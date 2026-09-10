set -u
umask 077
source /var/lib/cka-certificate-artifacts/state.sh || exit 1
source /var/lib/cka-certificate-artifacts/observe.sh || exit 1
source /var/lib/cka-certificate-artifacts/process.sh || exit 1
identity=$1; operation=$2; scenario=$3; root=/var/lib/cka-certificate-transaction
case $scenario in success|refusal|late-sync|post-rename|retained-output) ;; *) exit 2 ;; esac
declare -F cka_cert_decision_publish cka_cert_decision_reconcile >/dev/null || exit 3
cka_cert_state_init "$identity" && cka_cert_state_backup "$identity" || exit 4
cka_cert_process_stat "$BASHPID" || exit 5
owner_pid=$BASHPID
# Synthetic process decisions only. No command, renewal or recovery is launched.
before=$(jq -cn --argjson identity "$identity" --arg operation "$operation" --argjson pid "$owner_pid" \
  --arg ticks "$CKA_CERT_PROC_START" '{schema:2,identity:$identity,operation_id:$operation,
  stage:"launch_requested",coordinator:{pid:$pid,start_time:$ticks},supervisor:null,
  timeout_seconds:30,cancel_ack:false,cause:"none",launch_disposition:"not_committed",
  command:{started:null,child_pid:null,exit_code:null}}') || exit 6
next=$(jq -c '.stage="launch_committed" | .launch_disposition="supervisor_committed"' <<< "$before") || exit 7
absent='{"presence":"absent"}'
expected=$(jq -cn --argjson record "$before" '{presence:"present",record:$record}') || exit 8
budget() { cka_cert_process_now || exit 9; deadline=$((CKA_CERT_PROCESS_NOW + $1)); }
closed() { [[ ! -L /proc/$BASHPID/fd/8 && -z ${CKA_CERT_CONTROL_OWNER:-} && -z ${CKA_CERT_CONTROL_DELEGATED:-} ]]; }
budget 4000
cka_cert_control_init "$deadline" "$identity" "$operation" && cka_cert_control_open "$deadline" || exit 10
if [[ $scenario == refusal ]]; then
  ( if cka_cert_control_locked "$deadline" || cka_cert_control_close; then exit 1; fi
    cka_cert_control_child_drop && [[ ! -L /proc/$BASHPID/fd/8 ]] ) || exit 11
  request=$(jq -cn --argjson pid "$owner_pid" --arg ticks "$CKA_CERT_PROC_START" \
    --arg control "$(stat -Lc '%d:%i' /proc/$owner_pid/fd/8)" --arg state "$(stat -Lc '%d:%i' /proc/$owner_pid/fd/9)" \
    --argjson proposal "$(cka_cert_decision_proposal "$identity" "$operation" "$absent" "$before")" \
    '{owner:{pid:$pid,start_time:$ticks},control:$control,state:$state,proposal:$proposal}') || exit 52
  ( unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED CKA_CERT_CONTROL_DELEGATED
    if cka_cert_decision_executor publish "$request"; then exit 1; fi ) || exit 53
  CKA_CERT_CONTROL_DELEGATED=$BASHPID
  ( cka_cert_control_child_drop && [[ ! -L /proc/$BASHPID/fd/8 && -z ${CKA_CERT_CONTROL_DELEGATED:-} ]] ) || exit 66
  if cka_cert_control_acquire "$deadline" || cka_cert_control_locked "$deadline" ||
    cka_cert_decision_publish "$deadline" "$identity" "$operation" "$absent" "$before"; then exit 12; fi
  [[ -z ${CKA_CERT_DECISION_RESULT+x} ]] || exit 13
  cka_cert_control_close && closed || exit 14
  cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$absent" "$before" || exit 15
  [[ $CKA_CERT_DECISION_RESULT == predecessor && ! -e $root/process.json ]] && closed || exit 16
else
  cka_cert_decision_publish "$deadline" "$identity" "$operation" "$absent" "$before" || exit 17
  [[ $CKA_CERT_DECISION_RESULT == reconciliation_required ]] && closed || exit 18
  if cka_cert_decision_publish "$deadline" "$identity" "$operation" "$expected" "$next"; then exit 19; fi
  [[ -z ${CKA_CERT_DECISION_RESULT+x} ]] || exit 20
  cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$absent" "$before" || exit 21
  [[ $CKA_CERT_DECISION_RESULT == successor ]] && closed || exit 22
  cka_cert_control_open "$deadline" || exit 23
  if [[ $scenario == success ]]; then
    shim=$(mktemp -d "$root/reentry.XXXXXXXX") || exit 54
    CKA_TEST_REAL_JQ=$(command -v jq); CKA_TEST_OWNER=$BASHPID; export CKA_TEST_REAL_JQ CKA_TEST_OWNER
    printf '%s\n' '#!/bin/bash' '[[ $1 != -es ]] || kill -USR1 "$CKA_TEST_OWNER"' \
      'exec "$CKA_TEST_REAL_JQ" "$@"' > "$shim/jq"
    chmod 700 "$shim/jq" || exit 55
    trap 'if cka_cert_control_acquire "$deadline"; then reentry=accepted; else reentry=refused; fi' USR1
    original_path=$PATH; PATH=$shim:$PATH; export PATH
    cka_cert_decision_publish "$deadline" "$identity" "$operation" "$expected" "$next" || exit 24
    PATH=$original_path; export PATH; trap - USR1
    [[ ${reentry:-} == refused ]] || exit 56
    closed || exit 25
    cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$expected" "$next" || exit 26
    [[ $CKA_CERT_DECISION_RESULT == successor ]] && closed || exit 27
    before_hash=$(sha256sum "$root/process.json") || exit 28
    cka_cert_control_open "$deadline" || exit 29
    if cka_cert_decision_publish "$deadline" "$identity" "$operation" "$expected" "$next"; then exit 30; fi
    [[ -z ${CKA_CERT_DECISION_RESULT+x} && $(sha256sum "$root/process.json") == "$before_hash" ]] && closed || exit 31
    conflict=$(jq -c '.timeout_seconds=31' <<< "$next") || exit 32
    cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$absent" "$conflict" || exit 33
    [[ $CKA_CERT_DECISION_RESULT == conflict && $(sha256sum "$root/process.json") == "$before_hash" ]] && closed || exit 34
    # Inject missing/null records under custody; restoration below is test cleanup,
    # never production reconciliation or certificate rollback evidence.
    cka_cert_control_open "$deadline" && mv "$root/process.json" "$root/test-original.json" && cka_cert_control_close || exit 57
    cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$expected" "$next" || exit 58
    [[ $CKA_CERT_DECISION_RESULT == missing && ! -e $root/process.json ]] || exit 59
    cka_cert_control_open "$deadline" || exit 60
    printf 'null\n' > "$root/process.json"; cka_cert_control_close || exit 61
    if cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$expected" "$next"; then exit 62; fi
    [[ -z ${CKA_CERT_DECISION_RESULT+x} && $(cat "$root/process.json") == null ]] && closed || exit 63
    cka_cert_control_open "$deadline" && mv -T "$root/test-original.json" "$root/process.json" && cka_cert_control_close || exit 64
    [[ $(sha256sum "$root/process.json") == "$before_hash" ]] || exit 65
  else
    # Explicit finite fault injection, not an observed production incident.
    case $scenario in late-sync) tool=sync ;; post-rename) tool=mv ;; retained-output) tool=jq ;; esac
    CKA_TEST_REAL_TOOL=$(command -v "$tool") || exit 35
    export CKA_TEST_REAL_TOOL
    shim=$(mktemp -d "$root/fault.XXXXXXXX") || exit 36
    CKA_TEST_MARKER=$shim/entered; export CKA_TEST_MARKER
    cat > "$shim/$tool" <<'SH'
#!/bin/bash
trap '' TERM HUP INT
case ${0##*/} in
  sync) if [[ $1 == -f && $2 == */decision.* ]]; then printf 'sync\n' > "$CKA_TEST_MARKER"; sleep 6; fi ;;
  mv) "$CKA_TEST_REAL_TOOL" "$@" || exit; printf 'mv\n' > "$CKA_TEST_MARKER"; sleep 6; exit 0 ;;
  jq) if [[ $1 == -es ]]; then printf 'jq\n' > "$CKA_TEST_MARKER"; sleep 6; fi ;;
esac
exec "$CKA_TEST_REAL_TOOL" "$@"
SH
    chmod 700 "$shim/$tool" || exit 37
    original_path=$PATH; PATH=$shim:$PATH; export PATH
    budget 300; started=$CKA_CERT_PROCESS_NOW
    if cka_cert_decision_publish "$deadline" "$identity" "$operation" "$expected" "$next"; then exit 38; else result=$?; fi
    PATH=$original_path; export PATH
    cka_cert_process_now || exit 39
    elapsed=$((CKA_CERT_PROCESS_NOW-started))
    (( elapsed < 450 && (result == 124 || result == 137) )) || exit 40
    [[ -z ${CKA_CERT_DECISION_RESULT+x} ]] && closed || exit 41
    [[ -f $CKA_TEST_MARKER && $(cat "$CKA_TEST_MARKER") == "$tool" ]] || exit 67
    # Drop our own FD9 before testing both independent descriptions against survivors.
    exec 9>&-; unset CKA_CERT_STATE_OWNS_FD
    budget 4000
    if cka_cert_control_open "$deadline"; then exit 42; fi
    if flock -n "$root/lock" true; then exit 43; fi
    sleep 7
    cka_cert_state_lock || exit 44
    cka_cert_decision_reconcile "$deadline" "$identity" "$operation" "$expected" "$next" || exit 45
    if [[ $scenario == post-rename ]]; then
      [[ $CKA_CERT_DECISION_RESULT == successor ]] || exit 46
    else [[ $CKA_CERT_DECISION_RESULT == predecessor ]] || exit 47; fi
    closed || exit 48
    printf 'FAULT_RESULT %s %s %s\n' "$scenario" "$result" "$elapsed"
  fi
fi
[[ ! -e $root/command.json && ! -e $root/cancel.json ]] || exit 49
cka_cert_state_close || exit 50
# Fresh independent custody after the harmless case; no surviving holder may remain.
flock -n "$root/control.lock" true && flock -n "$root/lock" true || exit 51
printf 'CASE_PASS %s\nDECISION_PUBLICATION_PASS\n' "$scenario"
