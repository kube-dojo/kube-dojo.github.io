# Packet T3 rollback: restore backup apiserver pair after verified renew.
# Source after state.sh + observe.sh + renew.sh with FD9 held.

cka_cert_rollback_write() {
  local state temporary
  [[ $# == 1 ]] || return 1
  state=$1
  temporary=$(mktemp /var/lib/cka-certificate-transaction/state.XXXXXXXX) || return 1
  cka_cert_state_file "$temporary" || return 1
  printf '%s\n' "$state" > "$temporary" || return 1
  sync -f "$temporary" || return 1
  mv -T -- "$temporary" /var/lib/cka-certificate-transaction/state.json || return 1
  sync -f /var/lib/cka-certificate-transaction || return 1
}

cka_cert_rollback_begin() {
  local expected state
  [[ $# == 1 ]] || return 1
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  jq -e '.recovery.direction=="forward" and .recovery.stage=="manifest_returned"' \
    <<< "$state" >/dev/null || return 1
  state=$(jq -c '.recovery={direction:"rollback",stage:"rollback_requested"} | .revision+=1' \
    <<< "$state") || return 1
  cka_cert_rollback_write "$state"
}

cka_cert_rollback_phase() {
  local expected state from to
  [[ $# == 3 ]] || return 1
  from=$2; to=$3
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  jq -e --arg from "$from" '
    .recovery.direction=="rollback" and .recovery.stage==$from
  ' <<< "$state" >/dev/null || return 1
  state=$(jq -c --arg to "$to" '.recovery.stage=$to | .revision+=1' <<< "$state") || return 1
  cka_cert_rollback_write "$state"
}

cka_cert_rollback_stop_consumer() {
  local staged
  [[ $# == 1 ]] || return 1
  cka_cert_rollback_phase "$1" rollback_requested consumer_stop_requested || return 1
  staged=/var/lib/cka-certificate-transaction/kube-apiserver.yaml.rollback
  [[ ! -e $staged && ! -L $staged ]] || return 1
  [[ -f /etc/kubernetes/manifests/kube-apiserver.yaml &&
     ! -L /etc/kubernetes/manifests/kube-apiserver.yaml ]] || return 1
  (umask 077; set -o noclobber; cat -- /etc/kubernetes/manifests/kube-apiserver.yaml > "$staged") || return 1
  cka_cert_state_file "$staged" || return 1
  cmp -s -- /etc/kubernetes/manifests/kube-apiserver.yaml "$staged" || return 1
  rm -f -- /etc/kubernetes/manifests/kube-apiserver.yaml || return 1
  [[ ! -e /etc/kubernetes/manifests/kube-apiserver.yaml ]] || return 1
  cka_cert_rollback_phase "$1" consumer_stop_requested consumer_stopped || return 1
}

# Resumes from pair_restore_requested after partial failure. Args: id CRI_BIN endpoint
cka_cert_rollback_restore_pair() {
  local expected state ids stage after backup_fp temporary
  [[ $# == 3 ]] || return 1
  ids=$(cka_cert_obs_running_ids "$2" "$3") || return 1
  [[ $ids == '[]' ]] || return 1
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  stage=$(jq -er '.recovery.stage' <<< "$state") || return 1
  backup_fp=$(jq -er '.baseline.fingerprint' <<< "$state") || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/apiserver.crt || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/apiserver.key || return 1
  if [[ $stage == consumer_stopped ]]; then
    cka_cert_rollback_phase "$1" consumer_stopped pair_restore_requested || return 1
  elif [[ $stage != pair_restore_requested ]]; then
    return 1
  fi
  if ! cmp -s -- /var/lib/cka-certificate-transaction/apiserver.crt /etc/kubernetes/pki/apiserver.crt ||
     ! cmp -s -- /var/lib/cka-certificate-transaction/apiserver.key /etc/kubernetes/pki/apiserver.key; then
    temporary=$(mktemp /etc/kubernetes/pki/apiserver.crt.XXXXXXXX) || return 1
    cat -- /var/lib/cka-certificate-transaction/apiserver.crt > "$temporary" || return 1
    mv -T -- "$temporary" /etc/kubernetes/pki/apiserver.crt || return 1
    temporary=$(mktemp /etc/kubernetes/pki/apiserver.key.XXXXXXXX) || return 1
    cat -- /var/lib/cka-certificate-transaction/apiserver.key > "$temporary" || return 1
    mv -T -- "$temporary" /etc/kubernetes/pki/apiserver.key || return 1
    sync -f /etc/kubernetes/pki/apiserver.crt /etc/kubernetes/pki/apiserver.key || return 1
    cmp -s -- /var/lib/cka-certificate-transaction/apiserver.crt /etc/kubernetes/pki/apiserver.crt || return 1
    cmp -s -- /var/lib/cka-certificate-transaction/apiserver.key /etc/kubernetes/pki/apiserver.key || return 1
  fi
  after=$(cka_cert_renew_cert_fingerprint) || return 1
  [[ $after == "$backup_fp" ]] || return 1
  cka_cert_rollback_phase "$1" pair_restore_requested pair_restored || return 1
}

cka_cert_rollback_return_manifest() {
  local backup
  [[ $# == 1 ]] || return 1
  backup=/var/lib/cka-certificate-transaction/kube-apiserver.yaml
  cka_cert_state_file "$backup" || return 1
  [[ ! -e /etc/kubernetes/manifests/kube-apiserver.yaml &&
     ! -L /etc/kubernetes/manifests/kube-apiserver.yaml ]] || return 1
  cka_cert_rollback_phase "$1" pair_restored manifest_return_requested || return 1
  (umask 022; set -o noclobber; cat -- "$backup" > /etc/kubernetes/manifests/kube-apiserver.yaml) || return 1
  cmp -s -- "$backup" /etc/kubernetes/manifests/kube-apiserver.yaml || return 1
  cka_cert_rollback_phase "$1" manifest_return_requested manifest_returned || return 1
}

cka_cert_rollback_verify() {
  local expected state fp baseline
  [[ $# == 1 ]] || return 1
  cka_cert_state_environment && cka_cert_state_locked || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  jq -e '.recovery.direction=="rollback" and .recovery.stage=="manifest_returned"' \
    <<< "$state" >/dev/null || return 1
  baseline=$(jq -er '.baseline.fingerprint' <<< "$state") || return 1
  fp=$(cka_cert_renew_cert_fingerprint) || return 1
  [[ $fp == "$baseline" ]] || return 1
  cka_cert_rollback_phase "$1" manifest_returned rollback_verified || return 1
}
