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
    select(.artifact_hashes | type=="object" and keys==["observe.sh","state.sh"] and
      all(.[]; hex))
  ' <<< "$1"
}

cka_cert_state_artifacts() {
  local name actual expected
  [[ $# == 1 ]] || return 1
  cka_cert_state_directory /var/lib/cka-certificate-artifacts || return 1
  for name in state.sh observe.sh; do
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
  [[ $# == 1 ]] || return 1
  cka_cert_state_directory /var/lib/cka-certificate-transaction || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/state.json || return 1
  jq -ces --argjson expected "$1" '
    if length==1 then .[0] else error("Expected one state") end |
    select(type=="object" and keys==["identity","recovery","revision","schema"]) |
    select(.schema==1 and .revision==0 and .identity==$expected) |
    select(.recovery=={direction:"forward",stage:"created"})
  ' /var/lib/cka-certificate-transaction/state.json
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
