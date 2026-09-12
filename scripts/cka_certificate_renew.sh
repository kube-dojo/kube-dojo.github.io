# In-node apiserver serving-certificate renew primitives (Packet T2).
# Source after state.sh + observe.sh with FD9 held and backup_verified.
# No private-key egress. Rollback helpers are a separate packet.

# Record a forward recovery stage. Caller must already hold the lock.
cka_cert_renew_phase() {
  local expected state temporary from to
  [[ $# == 3 ]] || return 1
  from=$2; to=$3
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  jq -e --arg from "$from" '
    .recovery.direction=="forward" and .recovery.stage==$from
  ' <<< "$state" >/dev/null || return 1
  state=$(jq -c --arg to "$to" '.recovery.stage=$to | .revision+=1' <<< "$state") || return 1
  temporary=$(mktemp /var/lib/cka-certificate-transaction/state.XXXXXXXX) || return 1
  cka_cert_state_file "$temporary" || return 1
  printf '%s\n' "$state" > "$temporary" || return 1
  sync -f "$temporary" || return 1
  mv -T -- "$temporary" /var/lib/cka-certificate-transaction/state.json || return 1
  sync -f /var/lib/cka-certificate-transaction || return 1
}

# Stage a byte-identical manifest copy, then remove the watched file (stop consumer).
cka_cert_renew_stop_consumer() {
  local staged
  [[ $# == 1 ]] || return 1
  cka_cert_renew_phase "$1" backup_verified consumer_stop_requested || return 1
  staged=/var/lib/cka-certificate-transaction/kube-apiserver.yaml.live
  [[ ! -e $staged && ! -L $staged ]] || return 1
  [[ -f /etc/kubernetes/manifests/kube-apiserver.yaml &&
     ! -L /etc/kubernetes/manifests/kube-apiserver.yaml ]] || return 1
  (umask 077; set -o noclobber; cat -- /etc/kubernetes/manifests/kube-apiserver.yaml > "$staged") || return 1
  cka_cert_state_file "$staged" || return 1
  cmp -s -- /etc/kubernetes/manifests/kube-apiserver.yaml "$staged" || return 1
  rm -f -- /etc/kubernetes/manifests/kube-apiserver.yaml || return 1
  [[ ! -e /etc/kubernetes/manifests/kube-apiserver.yaml ]] || return 1
  cka_cert_renew_phase "$1" consumer_stop_requested consumer_stopped || return 1
}

# Poll CRI until no kube-apiserver container is running (max attempts).
# Args: attempts, CRI_BIN, unix://CRI_ENDPOINT
cka_cert_renew_wait_stopped() {
  local attempts ids
  [[ $# == 3 && $1 =~ ^[1-9][0-9]*$ ]] || return 1
  attempts=$1
  while (( attempts > 0 )); do
    ids=$(cka_cert_obs_running_ids "$2" "$3") || return 1
    [[ $ids == '[]' ]] && return 0
    attempts=$((attempts - 1))
    sleep 1
  done
  return 124
}

# Live cert+key identity only (no manifest). Prints lowercase 64-hex fingerprint.
# Pair match is proven by successful cka_cert_obs_pair; private key never printed.
cka_cert_renew_cert_fingerprint() {
  local fingerprint
  [[ $# == 0 ]] || return 1
  declare -F cka_cert_obs_fingerprint cka_cert_obs_pair >/dev/null || return 1
  [[ -f /etc/kubernetes/pki/apiserver.crt && ! -L /etc/kubernetes/pki/apiserver.crt ]] || return 1
  [[ -f /etc/kubernetes/pki/apiserver.key && ! -L /etc/kubernetes/pki/apiserver.key ]] || return 1
  fingerprint=$(cka_cert_obs_fingerprint /etc/kubernetes/pki/apiserver.crt) || return 1
  fingerprint=${fingerprint#*=}
  fingerprint=${fingerprint//:/}
  fingerprint=${fingerprint,,}
  cka_cert_obs_pair /etc/kubernetes/pki/apiserver.crt /etc/kubernetes/pki/apiserver.key >/dev/null || return 1
  [[ $fingerprint =~ ^[a-f0-9]{64}$ ]] || return 1
  printf '%s\n' "$fingerprint"
}

# Renew only apiserver; require consumer stopped; fingerprint must change + pair match.
# Args: identity, CRI_BIN, unix://CRI_ENDPOINT
cka_cert_renew_apiserver() {
  local before after ids
  [[ $# == 3 ]] || return 1
  ids=$(cka_cert_obs_running_ids "$2" "$3") || return 1
  [[ $ids == '[]' ]] || return 1
  before=$(cka_cert_renew_cert_fingerprint) || return 1
  cka_cert_renew_phase "$1" consumer_stopped renew_requested || return 1
  kubeadm certs renew apiserver || return 1
  after=$(cka_cert_renew_cert_fingerprint) || return 1
  [[ $after != "$before" ]] || return 1
  cka_cert_renew_phase "$1" renew_requested renew_verified || return 1
}

# Return the staged (unchanged) manifest to the static-pod watch directory.
cka_cert_renew_return_manifest() {
  local staged
  [[ $# == 1 ]] || return 1
  staged=/var/lib/cka-certificate-transaction/kube-apiserver.yaml.live
  cka_cert_state_file "$staged" || return 1
  [[ ! -e /etc/kubernetes/manifests/kube-apiserver.yaml &&
     ! -L /etc/kubernetes/manifests/kube-apiserver.yaml ]] || return 1
  cka_cert_renew_phase "$1" renew_verified manifest_return_requested || return 1
  (umask 022; set -o noclobber; cat -- "$staged" > /etc/kubernetes/manifests/kube-apiserver.yaml) || return 1
  cmp -s -- "$staged" /etc/kubernetes/manifests/kube-apiserver.yaml || return 1
  cka_cert_renew_phase "$1" manifest_return_requested manifest_returned || return 1
}
