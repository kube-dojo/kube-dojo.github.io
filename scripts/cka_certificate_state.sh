# Internal Linux Bash library: sourcing defines functions only.
# Host verifies Docker identity independently; these functions do not prove it.
# Requires root, /proc, jq, flock and GNU stat, sha256sum, mktemp, sync, mv.

cka_cert_state_file() {
  [[ $# == 1 ]] || return 1
  [[ -f $1 && ! -L $1 ]] && [[ $(stat -c '%u:%a:%h' -- "$1") == 0:600:1 ]]
}

cka_cert_state_environment() {
  local path mode
  [[ $# == 0 && $EUID == 0 && -d /proc/$BASHPID/fd ]] || return 1
  for path in / /var /var/lib; do
    [[ -d $path && ! -L $path && $(stat -c %u -- "$path") == 0 ]] || return 1
    mode=$(stat -c %a -- "$path") || return 1
    (( (8#$mode & 0022) == 0 )) || return 1
  done
}

cka_cert_state_directory() {
  [[ $# == 1 ]] || return 1
  [[ -d $1 && ! -L $1 ]] && [[ $(stat -c '%u:%a' -- "$1") == 0:700 ]]
}

cka_cert_state_expected() {
  [[ $# == 1 ]] || return 1
  jq -ces '
    def hex: type=="string" and test("^[a-f0-9]{64}$");
    if length==1 then .[0] else error("Expected one identity") end |
    select(type=="object") |
    select(keys==["artifact_hashes","docker_container_id","fixture_cluster",
      "image_id","system_namespace_uid","transaction_id"]) |
    select(.transaction_id | type=="string" and test("^[a-f0-9]{32}$")) |
    select(.fixture_cluster | type=="string" and test("^cert-fixture-[a-f0-9]{32}$")) |
    select(.docker_container_id | hex) |
    select(.image_id | type=="string" and test("^sha256:[a-f0-9]{64}$")) |
    select(.system_namespace_uid | type=="string" and
      test("^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")) |
    select(.artifact_hashes | type=="object" and keys==["observe.sh","process.sh","state.sh"] and
      all(.[]; hex))
  ' <<< "$1"
}

cka_cert_state_artifacts() {
  local name actual expected
  [[ $# == 1 ]] || return 1
  cka_cert_state_directory /var/lib/cka-certificate-artifacts || return 1
  for name in state.sh observe.sh process.sh; do
    cka_cert_state_file "/var/lib/cka-certificate-artifacts/$name" || return 1
    actual=$(sha256sum -- "/var/lib/cka-certificate-artifacts/$name") || return 1
    expected=$(jq -er --arg name "$name" '.artifact_hashes[$name]' <<< "$1") || return 1
    [[ ${actual%% *} == "$expected" ]] || return 1
  done
}

cka_cert_state_lock() {
  [[ $# == 0 && -d /proc/$BASHPID/fd && ! -L /proc/$BASHPID/fd/9 ]] || return 1
  cka_cert_state_directory /var/lib/cka-certificate-transaction || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/lock || return 1
  exec 9<> /var/lib/cka-certificate-transaction/lock || return 1
  CKA_CERT_STATE_OWNS_FD=1
  cka_cert_state_locked || { exec 9>&-; unset CKA_CERT_STATE_OWNS_FD; return 1; }
}

cka_cert_state_descriptor() {
  [[ $# == 0 && ${CKA_CERT_STATE_OWNS_FD:-0} == 1 && -L /proc/$BASHPID/fd/9 ]] || return 1
  local descriptor inode
  cka_cert_state_file /var/lib/cka-certificate-transaction/lock || return 1
  descriptor=$(stat -Lc '%d:%i' -- /proc/$BASHPID/fd/9) || return 1
  inode=$(stat -c '%d:%i' -- /var/lib/cka-certificate-transaction/lock) || return 1
  [[ $descriptor == "$inode" ]]
}

cka_cert_state_locked() {
  [[ $# == 0 ]] && cka_cert_state_descriptor && flock -n 9
}

# Closing the local descriptor preserves any lock inherited by a live child.
cka_cert_state_close() {
  [[ $# == 0 && ${CKA_CERT_STATE_OWNS_FD:-0} == 1 ]] || return 1
  cka_cert_state_descriptor || return 1
  exec 9>&- || return 1
  unset CKA_CERT_STATE_OWNS_FD
}

cka_cert_state_read() {
  local state revision
  [[ $# == 1 ]] || return 1
  cka_cert_state_directory /var/lib/cka-certificate-transaction || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/state.json || return 1
  state=$(jq -ces --argjson expected "$1" '
    def hash: type=="string" and test("^[a-f0-9]{64}$");
    def files: type=="object" and keys==["apiserver.crt","apiserver.key","kube-apiserver.yaml"];
    if length==1 then .[0] else error("Expected one state") end |
    select(type=="object" and .schema==1 and .identity==$expected) |
    select(if .revision==0 then
      keys==["identity","recovery","revision","schema"] and
      .recovery=={direction:"forward",stage:"created"}
    else
      keys==["baseline","identity","recovery","revision","schema"] and
      ((.revision==1 and .recovery=={direction:"forward",stage:"backup_requested"}) or
       (.revision==2 and .recovery=={direction:"forward",stage:"backup_verified"}) or
       (.revision>=3 and .recovery.direction=="forward" and
         (.recovery.stage | IN("consumer_stop_requested","consumer_stopped",
           "renew_requested","renew_verified","manifest_return_requested",
           "manifest_returned")))) and
      (.baseline | type=="object" and keys==["fingerprint","hashes","metadata","public_key"] and
        (.fingerprint | hash) and (.public_key | hash) and
        (.hashes | files and all(.[]; hash)) and
        (.metadata | files and all(.[];
          type=="object" and keys==["gid","mode","uid"] and .uid==0 and
          (.gid | type=="number" and .>=0 and floor==.) and
          (.mode=="600" or .mode=="644")) and .["apiserver.key"].mode=="600"))
    end)
  ' /var/lib/cka-certificate-transaction/state.json) || return 1
  revision=$(jq -r .revision <<< "$state") || return 1
  if [[ $revision == 2 ]]; then
    cka_cert_state_backup_verify "$state" || return 1
  fi
  printf '%s\n' "$state"
}

cka_cert_state_init() {
  local expected temporary
  [[ $# == 1 && ! -L /proc/$BASHPID/fd/9 ]] || return 1
  cka_cert_state_environment || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  mkdir -m 0700 /var/lib/cka-certificate-transaction || return 1
  (umask 077; set -o noclobber; : > /var/lib/cka-certificate-transaction/lock) || return 1
  cka_cert_state_lock || return 1
  temporary=$(mktemp /var/lib/cka-certificate-transaction/state.XXXXXXXX) || {
    cka_cert_state_close; return 1;
  }
  if ! cka_cert_state_file "$temporary" ||
     ! jq -cn --argjson identity "$expected" \
       '{schema:1,identity:$identity,revision:0,recovery:{direction:"forward",stage:"created"}}' > "$temporary" ||
     ! sync -f "$temporary" ||
     ! mv -T -- "$temporary" /var/lib/cka-certificate-transaction/state.json ||
     ! sync -f /var/lib/cka-certificate-transaction; then
    cka_cert_state_close
    return 1
  fi
}

cka_cert_state_open() {
  local expected
  [[ $# == 1 && ! -L /proc/$BASHPID/fd/9 ]] || return 1
  cka_cert_state_environment || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  cka_cert_state_lock || return 1
  cka_cert_state_read "$expected" >/dev/null || { cka_cert_state_close; return 1; }
}

# Status requires an already held lock; it never opens or creates transaction files.
cka_cert_state_status() {
  local expected state
  [[ $# == 1 ]] || return 1
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  jq -ce '{schema,identity,revision,recovery}' <<< "$state"
}

# Key bytes travel only between file descriptors; hashes remain private state.
cka_cert_state_backup_evidence() {
  local path mode name file digest metadata fingerprint public_key result='{"hashes":{},"metadata":{}}'
  [[ $# == 1 && ( $1 == live || $1 == backup ) ]] || return 1
  declare -F cka_cert_obs_fingerprint cka_cert_obs_pair >/dev/null || return 1
  if [[ $1 == live ]]; then
    for path in /etc /etc/kubernetes /etc/kubernetes/pki /etc/kubernetes/manifests; do
      [[ -d $path && ! -L $path && $(stat -c %u -- "$path") == 0 ]] || return 1
      mode=$(stat -c %a -- "$path") || return 1
      (( (8#$mode & 0022) == 0 )) || return 1
    done
  else
    cka_cert_state_directory /var/lib/cka-certificate-transaction || return 1
  fi
  for name in apiserver.crt apiserver.key kube-apiserver.yaml; do
    file="/var/lib/cka-certificate-transaction/$name"
    if [[ $1 == live ]]; then
      file="/etc/kubernetes/pki/$name"
      [[ $name != kube-apiserver.yaml ]] || file=/etc/kubernetes/manifests/kube-apiserver.yaml
      [[ -f $file && ! -L $file && $(stat -c '%u:%h' -- "$file") == 0:1 ]] || return 1
      mode=$(stat -c %a -- "$file") || return 1
      [[ $mode == 600 || ( $mode == 644 && $name != apiserver.key ) ]] || return 1
    else
      cka_cert_state_file "$file" || return 1
    fi
    digest=$(sha256sum -- "$file") || return 1
    metadata=$(stat -c '{"uid":%u,"gid":%g,"mode":"%a"}' -- "$file") || return 1
    result=$(jq -c --arg name "$name" --arg digest "${digest%% *}" --argjson metadata "$metadata" \
      '.hashes[$name]=$digest | .metadata[$name]=$metadata' <<< "$result") || return 1
  done
  path=/var/lib/cka-certificate-transaction
  [[ $1 != live ]] || path=/etc/kubernetes/pki
  fingerprint=$(cka_cert_obs_fingerprint "$path/apiserver.crt") || return 1
  fingerprint=${fingerprint#*=}
  fingerprint=${fingerprint//:/}
  public_key=$(cka_cert_obs_pair "$path/apiserver.crt" "$path/apiserver.key") || return 1
  public_key=${public_key##* }
  [[ ${fingerprint,,} =~ ^[a-f0-9]{64}$ && $public_key =~ ^[a-f0-9]{64}$ ]] || return 1
  jq -c --arg fingerprint "${fingerprint,,}" --arg public_key "$public_key" \
    '. + {fingerprint:$fingerprint,public_key:$public_key}' <<< "$result"
}

cka_cert_state_backup_verify() {
  local evidence
  [[ $# == 1 ]] || return 1
  evidence=$(cka_cert_state_backup_evidence backup) || return 1
  jq -e --argjson evidence "$evidence" \
    '(.baseline | del(.metadata))==($evidence | del(.metadata))' <<< "$1" >/dev/null
}

# No retry/adoption API: a partial copy remains backup_requested for reconciliation.
cka_cert_state_backup() {
  local expected state baseline current stage revision temporary name source target
  [[ $# == 1 ]] || return 1
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  [[ $(jq -r .revision <<< "$state") == 0 ]] || return 1
  baseline=$(cka_cert_state_backup_evidence live) || return 1
  for name in apiserver.crt apiserver.key kube-apiserver.yaml; do
    target="/var/lib/cka-certificate-transaction/$name"
    [[ ! -e $target && ! -L $target ]] || return 1
  done
  revision=0
  for stage in backup_requested backup_verified; do
    cka_cert_state_environment && cka_cert_state_locked || return 1
    cka_cert_state_artifacts "$expected" || return 1
    current=$(cka_cert_state_read "$expected") || return 1
    [[ $current == "$state" ]] || return 1
    revision=$((revision + 1))
    state=$(jq -c --argjson baseline "$baseline" --arg stage "$stage" --argjson revision "$revision" \
      '.baseline=$baseline | .revision=$revision | .recovery.stage=$stage' <<< "$state") || return 1
    temporary=$(mktemp /var/lib/cka-certificate-transaction/state.XXXXXXXX) || return 1
    cka_cert_state_file "$temporary" || return 1
    printf '%s\n' "$state" > "$temporary" || return 1
    sync -f "$temporary" || return 1
    mv -T -- "$temporary" /var/lib/cka-certificate-transaction/state.json || return 1
    sync -f /var/lib/cka-certificate-transaction || return 1
    [[ $stage != backup_verified ]] || return 0
    for name in apiserver.crt apiserver.key kube-apiserver.yaml; do
      source="/etc/kubernetes/pki/$name"
      [[ $name != kube-apiserver.yaml ]] || source=/etc/kubernetes/manifests/kube-apiserver.yaml
      target="/var/lib/cka-certificate-transaction/$name"
      (umask 077; set -o noclobber; cat -- "$source" > "$target") || return 1
      cka_cert_state_file "$target" && cmp -s -- "$source" "$target" || return 1
      sync -f "$target" || return 1
    done
    sync -f /var/lib/cka-certificate-transaction || return 1
    current=$(cka_cert_state_backup_evidence live) || return 1
    [[ $current == "$baseline" ]] || return 1
    cka_cert_state_backup_verify "$state" || return 1
  done
}
