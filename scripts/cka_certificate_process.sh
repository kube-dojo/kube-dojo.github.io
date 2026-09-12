# Internal Linux Bash process identity and private record custody primitives.
# Sourcing defines functions only. No launch, signalling or recovery admission.
# Callers explicitly source the state and observation helpers.
# Receipt publication additionally requires GNU ln and unlink.

# Parse after the LAST closing comm delimiter; spaces/parentheses in comm are valid.
# A vanished or malformed /proc entry is uncertainty, not proof of absence.
cka_cert_process_stat() {
  local line tail
  local -a fields
  [[ $# == 1 && $1 =~ ^[1-9][0-9]*$ ]] || return 1
  IFS= read -r line < "/proc/$1/stat" || return 1
  [[ $line == "$1 ("* && $line == *") "* ]] || return 1
  tail=${line##*) }
  read -r -a fields <<< "$tail" || return 1
  [[ ${#fields[@]} -ge 50 && ${fields[0]} =~ ^[RSDZTtXxKWPI]$ &&
     ${fields[1]} =~ ^[0-9]+$ && ${fields[2]} =~ ^[0-9]+$ &&
     ${fields[3]} =~ ^[0-9]+$ && ${fields[19]} =~ ^[0-9]+$ ]] || return 1
  CKA_CERT_PROC_STATE=${fields[0]}
  CKA_CERT_PROC_PPID=${fields[1]}
  CKA_CERT_PROC_PGID=${fields[2]}
  CKA_CERT_PROC_SID=${fields[3]}
  CKA_CERT_PROC_START=${fields[19]}
}

# Shared node clock in centiseconds, unlike shell-relative SECONDS.
# /proc/uptime reports elapsed boot time including suspend (proc_uptime(5)).
cka_cert_process_now() {
  local uptime idle extra
  [[ $# == 0 ]] || return 1
  read -r uptime idle extra < /proc/uptime || return 1
  [[ $uptime =~ ^[0-9]{1,12}\.[0-9]{2}$ && $idle =~ ^[0-9]+\.[0-9]{2}$ && -z $extra ]] || return 1
  CKA_CERT_PROCESS_NOW=$((10#${uptime%.*} * 100 + 10#${uptime#*.}))
}

# Pass an absolute deadline in node-clock centiseconds; callers share one budget.
# Builtins only while enumerating: do not manufacture transient scanner children.
# Zombies have released descriptors; any live reused SID conservatively blocks.
cka_cert_process_snapshot() {
  local path pid
  [[ $# == 3 && $1 =~ ^[1-9][0-9]*$ && $2 =~ ^[0-9]+$ && $3 =~ ^[0-9]{1,15}$ ]] || return 1
  CKA_CERT_PROCESS_OTHERS=0
  for path in /proc/[0-9]*/stat; do
    cka_cert_process_now || return 1
    (( CKA_CERT_PROCESS_NOW < 10#$3 )) || return 124
    pid=${path#/proc/}
    pid=${pid%/stat}
    cka_cert_process_stat "$pid" || return 1
    [[ $CKA_CERT_PROC_SID == "$1" ]] || continue
    [[ $CKA_CERT_PROC_STATE != Z && $CKA_CERT_PROC_STATE != X && $CKA_CERT_PROC_STATE != x ]] || continue
    [[ $CKA_CERT_PROC_PGID == "$1" ]] || return 1
    [[ $pid == "$2" ]] || CKA_CERT_PROCESS_OTHERS=$((CKA_CERT_PROCESS_OTHERS + 1))
  done
  cka_cert_process_now || return 1
  (( CKA_CERT_PROCESS_NOW < 10#$3 )) || return 124
}

cka_cert_process_check() {
  local expected state
  [[ $# == 2 && $2 =~ ^[a-f0-9]{32}$ ]] || return 1
  declare -F cka_cert_state_expected cka_cert_state_read cka_cert_state_artifacts \
    cka_cert_state_environment cka_cert_state_locked cka_cert_state_file >/dev/null || return 1
  cka_cert_state_environment || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  cka_cert_state_artifacts "$expected" || return 1
  state=$(cka_cert_state_read "$expected") || return 1
  jq -e '.revision==2 and .recovery=={direction:"forward",stage:"backup_verified"}' \
    <<< "$state" >/dev/null || return 1
}

# Validate both record kinds before either reading or creating a temporary file.
cka_cert_process_payload() {
  local expected
  [[ $# == 4 && $2 =~ ^[a-f0-9]{32}$ && ( $3 == process || $3 == cancel ) ]] || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  jq -ces --argjson identity "$expected" --arg operation "$2" --arg kind "$3" '
    def integer: type=="number" and floor==.;
    def pid: integer and .>0;
    def ticks: type=="string" and test("^[0-9]+$");
    def leader: type=="object" and keys==["pgid","pid","sid","start_time"] and
      (.pid | pid) and .pid==.pgid and .pid==.sid and (.start_time | ticks);
    def command: type=="object" and keys==["child_pid","exit_code","started"] and
      (if .started==true then (.child_pid | pid) and (.exit_code | integer and .>=0 and .<=255)
       else (.started==null or .started==false) and .child_pid==null and .exit_code==null end);
    if length==1 then .[0] else error("Expected one record") end |
    if $kind=="cancel" then
      select(.=={schema:1,identity:$identity,operation_id:$operation,request:"cancel"})
    else
      select(type=="object" and keys==["cancel_ack","cause","command","coordinator",
        "identity","launch_disposition","operation_id","schema","stage","supervisor","timeout_seconds"]) |
      select(.schema==2 and .identity==$identity and .operation_id==$operation) |
      select(.timeout_seconds | integer and .>=1 and .<=3600) |
      select(.cancel_ack | type=="boolean") |
      select(.cause=="none" or .cause=="cancel" or .cause=="timeout" or .cause=="signal" or .cause=="unknown") |
      select(.coordinator | type=="object" and keys==["pid","start_time"] and
        (.pid | pid) and (.start_time | ticks)) |
      select(.command | command) |
      select(if .stage=="launch_requested" then
        .supervisor==null and .launch_disposition=="not_committed" and .command.started==null and .cause=="none"
      elif .stage=="launch_committed" then
        .supervisor==null and .launch_disposition=="supervisor_committed" and .command.started==null and .cause=="none"
      elif .stage=="cancelled_before_launch" then
        (.supervisor==null or (.supervisor | leader)) and .launch_disposition=="not_started" and
        .command.started==false and .cancel_ack==true and .cause=="cancel"
      else
        (.supervisor | leader) and
        (if .stage=="supervisor_ready" then
          .launch_disposition=="supervisor_committed" and .command.started==null and .cause=="none"
        else .launch_disposition=="command_committed" and .command.started!=false and
          (if .stage=="command_launch_committed" then .command.started==null and .cause=="none"
           elif .stage=="term_requested" or .stage=="kill_requested" then .cause!="none" and .cause!="unknown"
           elif .stage=="supervision_complete" then .command.started==true and .cause!="unknown"
           elif .stage=="supervision_unresolved" then .cause!="none"
           else false end)
        end)
      end) |
      select(if .cancel_ack then .cause!="none" else .cause!="cancel" end)
    end
  ' <<< "$4"
}

cka_cert_process_read() {
  local payload
  [[ $# == 2 ]] || return 1
  cka_cert_state_environment || return 1
  cka_cert_state_directory /var/lib/cka-certificate-transaction || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/process.json || return 1
  payload=$(cat /var/lib/cka-certificate-transaction/process.json) || return 1
  cka_cert_process_payload "$1" "$2" process "$payload"
}

# Callers own sequencing. Process writes require FD9; cancel writes need no lock.
# Existing records must be private, valid and bound to this same operation.
cka_cert_process_write() {
  local temporary target payload existing
  [[ $# == 4 && ( $3 == process || $3 == cancel ) ]] || return 1
  cka_cert_process_check "$1" "$2" || return 1
  [[ $3 != process ]] || cka_cert_state_locked || return 1
  payload=$(cka_cert_process_payload "$1" "$2" "$3" "$4") || return 1
  target="/var/lib/cka-certificate-transaction/$3.json"
  if [[ -e $target || -L $target ]]; then
    cka_cert_state_file "$target" || return 1
    existing=$(cat -- "$target") || return 1
    cka_cert_process_payload "$1" "$2" "$3" "$existing" >/dev/null || return 1
  fi
  temporary=$(mktemp /var/lib/cka-certificate-transaction/process-write.XXXXXXXX) || return 1
  cka_cert_state_file "$temporary" || return 1
  printf '%s\n' "$payload" > "$temporary" || return 1
  sync -f "$temporary" || return 1
  mv -T -- "$temporary" "$target" || return 1
  sync -f /var/lib/cka-certificate-transaction || return 1
}

cka_cert_process_cancel_read() {
  local payload
  [[ $# == 2 && $2 =~ ^[a-f0-9]{32}$ ]] || return 1
  cka_cert_state_expected "$1" >/dev/null || return 1
  cka_cert_state_environment || return 1
  cka_cert_state_directory /var/lib/cka-certificate-transaction || return 1
  CKA_CERT_PROCESS_CANCEL=0
  if [[ ! -e /var/lib/cka-certificate-transaction/cancel.json &&
        ! -L /var/lib/cka-certificate-transaction/cancel.json ]]; then
    return 0
  fi
  cka_cert_state_file /var/lib/cka-certificate-transaction/cancel.json || return 1
  payload=$(cat /var/lib/cka-certificate-transaction/cancel.json) || return 1
  cka_cert_process_payload "$1" "$2" cancel "$payload" >/dev/null || return 1
  CKA_CERT_PROCESS_CANCEL=1
}

cka_cert_process_self() {
  [[ $# == 2 && $BASHPID == "$1" ]] || return 1
  cka_cert_process_stat "$1" || return 1
  [[ $CKA_CERT_PROC_PGID == "$1" && $CKA_CERT_PROC_SID == "$1" &&
     $CKA_CERT_PROC_START == "$2" ]]
}

# Expected identities must come from the later live supervisor/runner handshake.
cka_cert_supervisor_receipt_payload() {
  local expected
  [[ $# == 5 && $2 =~ ^[a-f0-9]{32}$ ]] || return 1
  expected=$(cka_cert_state_expected "$1") || return 1
  jq -ces --argjson identity "$expected" --arg operation "$2" \
    --argjson supervisor "$3" --argjson runner "$4" '
    def integer: type=="number" and floor==.;
    def pid: integer and .>0;
    def ticks: type=="string" and test("^[0-9]+$");
    def runner: type=="object" and keys==["pid","start_time"] and
      (.pid | pid) and (.start_time | ticks);
    def leader: type=="object" and keys==["pgid","pid","sid","start_time"] and
      (.pid | pid) and .pid==.pgid and .pid==.sid and (.start_time | ticks);
    if length==1 then .[0] else error("Expected one command receipt") end |
    select(($supervisor | leader) and ($runner | runner)) |
    select(type=="object" and keys==["child_pid","exit_code","identity","operation_id","runner","schema","supervisor"]) |
    select(.schema==1 and .identity==$identity and .operation_id==$operation and
      .supervisor==$supervisor and .runner==$runner and (.child_pid | pid)) |
    select(.exit_code | integer and .>=0 and .<=255)
  ' <<< "$5"
}

cka_cert_supervisor_receipt_read() {
  local payload
  [[ $# == 4 ]] || return 1
  cka_cert_process_check "$1" "$2" || return 1
  cka_cert_state_file /var/lib/cka-certificate-transaction/command.json || return 1
  payload=$(cat /var/lib/cka-certificate-transaction/command.json) || return 1
  cka_cert_supervisor_receipt_payload "$1" "$2" "$3" "$4" "$payload"
}

cka_cert_capture_directory() {
  [[ $# == 0 ]] && cka_cert_state_environment && cka_cert_state_directory /var/lib/cka-certificate-transaction
}

# Direct invocation only: never put this capture helper inside command substitution.
# Fixed single-line text results; uncertain files remain private reconciliation artifacts.
cka_cert_capture() {
  local deadline mode path snapshot
  unset CKA_CERT_CAPTURED
  [[ $# -ge 3 ]] || return 1
  deadline=$1; mode=$2; shift 2
  case "$mode:$1" in
    read:cka_cert_runner_payload|read:cka_cert_runner_read|read:cka_cert_runner_evidence|\
    read:cka_cert_runner_receipt_read|read:cka_cert_supervisor_receipt_payload|read:cka_cert_decision_observation|\
    read:cka_cert_decision_proposal|read:cka_cert_decision_classify|utility:jq|utility:mktemp|utility:stat) ;;
    *) return 1 ;;
  esac
  cka_cert_deadline_budget "$deadline" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_capture_directory || return $?
  path=/var/lib/cka-certificate-transaction/capture.$BASHPID.$RANDOM.$RANDOM
  [[ ! -e $path && ! -L $path ]] || return 1
  if (umask 077; set -C; exec 8>&-; {
    case $mode in
      read) cka_cert_run_read_helper "$deadline" "$@" ;;
      utility) cka_cert_run_utility "$deadline" -- "$@" ;;
    esac
  } > "$path" 2>&1); then :; else return $?; fi
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$path" || return $?
  # These allowlisted results are single-line text; cap the direct builtin read.
  if LC_ALL=C IFS= read -r -d '' -n 65537 snapshot < "$path"; then return 1; else [[ $? == 1 ]] || return 1; fi
  [[ ${#snapshot} -le 65536 && $snapshot == *$'\n' ]] || return 1
  snapshot=${snapshot%$'\n'}
  [[ -n $snapshot && $snapshot != *$'\n'* ]] || return 1
  cka_cert_deadline_budget "$deadline" || return $?
  CKA_CERT_CAPTURED=$snapshot
}

# Invoke directly in the admitted runner, not in a timeout-created Bash child.
# This proves writer identity/custody only; the runner must supply real wait evidence.
# Deadline is mandatory and first; late receipts are preserved without acknowledgement.
cka_cert_supervisor_receipt_write() {
  local deadline payload temporary runner_pid runner_start supervisor_pid supervisor_start
  [[ $# == 6 && ${CKA_CERT_STATE_OWNS_FD:-0} == 1 ]] || return 1
  deadline=$1
  cka_cert_capture "$deadline" read cka_cert_supervisor_receipt_payload "$2" "$3" "$4" "$5" "$6" || return $?
  payload=$CKA_CERT_CAPTURED
  cka_cert_run_read_helper "$deadline" cka_cert_process_check "$2" "$3" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_descriptor || return $?
  cka_cert_run_utility "$deadline" -- flock -n 9 || return $?
  cka_cert_capture "$deadline" utility jq -er .pid <<< "$5" || return $?
  runner_pid=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -er .start_time <<< "$5" || return $?
  runner_start=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -er .pid <<< "$4" || return $?
  supervisor_pid=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -er .start_time <<< "$4" || return $?
  supervisor_start=$CKA_CERT_CAPTURED
  [[ $BASHPID == "$runner_pid" ]] || return 1
  cka_cert_deadline_budget "$deadline" || return $?
  cka_cert_process_stat "$supervisor_pid" || return 1
  [[ $CKA_CERT_PROC_START == "$supervisor_start" && $CKA_CERT_PROC_PGID == "$supervisor_pid" &&
     $CKA_CERT_PROC_SID == "$supervisor_pid" ]] || return 1
  cka_cert_process_stat "$BASHPID" || return 1
  [[ $CKA_CERT_PROC_START == "$runner_start" && $CKA_CERT_PROC_PPID == "$supervisor_pid" &&
     $CKA_CERT_PROC_PGID == "$supervisor_pid" && $CKA_CERT_PROC_SID == "$supervisor_pid" ]] || return 1
  [[ ! -e /var/lib/cka-certificate-transaction/command.json &&
     ! -L /var/lib/cka-certificate-transaction/command.json ]] || return 1
  cka_cert_capture "$deadline" utility mktemp /var/lib/cka-certificate-transaction/command.XXXXXXXX || return $?
  temporary=$CKA_CERT_CAPTURED
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$temporary" || return $?
  cka_cert_deadline_budget "$deadline" || return $?
  printf '%s\n' "$payload" > "$temporary" || return 1
  cka_cert_run_utility "$deadline" -- sync -f "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- ln -T -- "$temporary" /var/lib/cka-certificate-transaction/command.json || return $?
  cka_cert_run_utility "$deadline" -- unlink -- "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- sync -f /var/lib/cka-certificate-transaction || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_supervisor_receipt_read "$2" "$3" "$4" "$5" >/dev/null
}

# Shared deadline helpers; source-inert. Deadline is absolute node centiseconds.
# A late/timeout result is unknown, never proof that descendants are absent.
cka_cert_deadline_budget() {
  local remaining soft
  [[ $# == 1 && $1 =~ ^[0-9]{1,15}$ ]] || return 1
  cka_cert_process_now || return 1
  remaining=$((10#$1 - CKA_CERT_PROCESS_NOW))
  # Reserve 25cs TERM-to-KILL grace and 5cs return margin inside this budget.
  (( remaining > 30 )) || return 124
  soft=$((remaining - 30))
  printf -v CKA_CERT_DEADLINE_SOFT '%d.%02ds' "$((soft / 100))" "$((soft % 100))"
}

# Use only for receipt/read utilities; never for authoritative decision publication.
# Decision publishers need a separate FD8+FD9-retaining protocol.
cka_cert_run_utility() {
  local deadline result duration
  [[ $# -ge 3 && $2 == -- ]] || return 1
  deadline=$1; shift 2
  case $1 in jq|stat|cat|sha256sum|sync|ln|unlink|mktemp|flock|cmp|openssl) ;; *) return 1 ;; esac
  cka_cert_deadline_budget "$deadline" || return $?
  duration=$CKA_CERT_DEADLINE_SOFT
  if (exec 8>&-; exec timeout --foreground --kill-after=0.25s "$duration" "$@"); then
    result=0
  else result=$?; fi
  cka_cert_process_now || return 1
  (( CKA_CERT_PROCESS_NOW < 10#$deadline )) || return 124
  return "$result"
}

# Fixed read-only function allowlist; no receipt writes or process decisions.
# Caller must have validated the private staged artifact set before dispatch.
cka_cert_run_read_helper() {
  local deadline duration result
  [[ $# -ge 2 ]] || return 1
  deadline=$1; shift
  case $1 in
    cka_cert_process_check|cka_cert_process_read|cka_cert_process_payload|cka_cert_capture_directory|\
    cka_cert_decision_observation|cka_cert_decision_proposal|cka_cert_decision_classify|\
    cka_cert_runner_payload|cka_cert_runner_live|cka_cert_runner_read|cka_cert_runner_permission|\
    cka_cert_runner_evidence|cka_cert_runner_receipt_read|cka_cert_runner_before|\
    cka_cert_state_expected|cka_cert_state_descriptor|cka_cert_state_file|\
    cka_cert_supervisor_receipt_payload|cka_cert_supervisor_receipt_read) ;;
    *) return 1 ;;
  esac
  cka_cert_deadline_budget "$deadline" || return $?
  duration=$CKA_CERT_DEADLINE_SOFT
  if (exec 8>&-; exec timeout --foreground --kill-after=0.25s "$duration" \
    env -u BASH_ENV -u ENV bash --noprofile --norc -p -c '
      unset CKA_CERT_CONTROL_OWNS_FD CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED
      source /var/lib/cka-certificate-artifacts/observe.sh || exit 1
      source /var/lib/cka-certificate-artifacts/state.sh || exit 1
      source /var/lib/cka-certificate-artifacts/process.sh || exit 1
      if [[ -L /proc/$BASHPID/fd/9 ]]; then
        CKA_CERT_STATE_OWNS_FD=1
        cka_cert_state_descriptor || exit 1
      fi
      "$@"
    ' cka-certificate-read-helper "$@"); then result=0; else result=$?; fi
  cka_cert_process_now || return 1
  (( CKA_CERT_PROCESS_NOW < 10#$deadline )) || return 124
  return "$result"
}

# Permanent control-inode custody. FD8 is reserved; callers must not replace it manually.
# Callers validate the private transaction directory; participating actors never replace the inode.
# Initialize once before process.json or any child work; failure requires reconciliation.
cka_cert_control_init() {
  local deadline temporary
  [[ $# == 3 && ${CKA_CERT_STATE_OWNS_FD:-0} == 1 ]] || return 1
  deadline=$1
  cka_cert_run_read_helper "$deadline" cka_cert_process_check "$2" "$3" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_descriptor || return $?
  cka_cert_run_utility "$deadline" -- flock -n 9 || return $?
  [[ ! -e /var/lib/cka-certificate-transaction/process.json &&
     ! -L /var/lib/cka-certificate-transaction/process.json &&
     ! -e /var/lib/cka-certificate-transaction/control.lock &&
     ! -L /var/lib/cka-certificate-transaction/control.lock ]] || return 1
  cka_cert_capture "$deadline" utility mktemp /var/lib/cka-certificate-transaction/control.XXXXXXXX || return $?
  temporary=$CKA_CERT_CAPTURED
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- sync -f "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- ln -T -- "$temporary" /var/lib/cka-certificate-transaction/control.lock || return $?
  cka_cert_run_utility "$deadline" -- unlink -- "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- sync -f /var/lib/cka-certificate-transaction || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_file /var/lib/cka-certificate-transaction/control.lock
}

cka_cert_control_descriptor() {
  local descriptor inode path
  [[ $# == 1 && -z ${CKA_CERT_CONTROL_DELEGATED:-} &&
     ${CKA_CERT_CONTROL_OWNER:-} == "$BASHPID" && -L /proc/$BASHPID/fd/8 ]] || return 1
  path=/proc/$BASHPID/fd/8
  cka_cert_run_read_helper "$1" cka_cert_state_file /var/lib/cka-certificate-transaction/control.lock || return $?
  cka_cert_capture "$1" utility stat -Lc '%d:%i:%u:%a:%h' -- "$path" || return $?
  descriptor=$CKA_CERT_CAPTURED
  cka_cert_capture "$1" utility stat -c '%d:%i:%u:%a:%h' -- /var/lib/cka-certificate-transaction/control.lock || return $?
  inode=$CKA_CERT_CAPTURED
  [[ $descriptor == "$inode" && $inode == *:0:600:1 ]]
}

# The only acquisition wrapper retaining FD8; never accepts arbitrary commands.
cka_cert_control_acquire() {
  local deadline duration result
  [[ $# == 1 && -z ${CKA_CERT_CONTROL_DELEGATED:-} &&
     ${CKA_CERT_CONTROL_OWNER:-} == "$BASHPID" && -L /proc/$BASHPID/fd/8 ]] || return 1
  deadline=$1
  cka_cert_deadline_budget "$deadline" || return $?
  duration=$CKA_CERT_DEADLINE_SOFT
  if timeout --foreground --kill-after=0.25s "$duration" flock -n 8; then result=0; else result=$?; fi
  cka_cert_process_now || return 1
  (( CKA_CERT_PROCESS_NOW < 10#$deadline )) || return 124
  return "$result"
}

cka_cert_control_close() {
  [[ $# == 0 && ${CKA_CERT_CONTROL_OWNER:-} == "$BASHPID" ]] || return 1
  exec 8>&- || return 1
  unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED CKA_CERT_CONTROL_DELEGATED
}

cka_cert_control_open() {
  [[ $# == 1 && -z ${CKA_CERT_CONTROL_OWNER:-} && ! -L /proc/$BASHPID/fd/8 ]] || return 1
  cka_cert_run_read_helper "$1" cka_cert_state_file /var/lib/cka-certificate-transaction/control.lock || return $?
  cka_cert_deadline_budget "$1" || return $?
  # Read-only open cannot recreate a vanished inode; native Linux flock permits it.
  exec 8< /var/lib/cka-certificate-transaction/control.lock || return 1
  CKA_CERT_CONTROL_OWNER=$BASHPID
  CKA_CERT_CONTROL_LOCKED=0
  if cka_cert_control_descriptor "$1" && cka_cert_control_acquire "$1" && cka_cert_control_descriptor "$1"; then
    CKA_CERT_CONTROL_LOCKED=1
  else
    local result=$?
    cka_cert_control_close || return 1
    return "$result"
  fi
}

cka_cert_control_locked() {
  [[ $# == 1 && ${CKA_CERT_CONTROL_LOCKED:-0} == 1 ]] || return 1
  cka_cert_control_descriptor "$1"
}

# Child bootstrap only, before doing any other work or acquiring a fresh lock.
cka_cert_control_child_drop() {
  [[ $# == 0 && ${CKA_CERT_CONTROL_OWNER:-} =~ ^[1-9][0-9]*$ &&
     $CKA_CERT_CONTROL_OWNER != "$BASHPID" ]] || return 1
  exec 8>&- || return 1
  unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED CKA_CERT_CONTROL_DELEGATED
}

# Pure record helpers only. Run through bounded read/capture dispatch in live callers.
# Explicit presence prevents a stored JSON null from masquerading as file absence.
cka_cert_decision_observation() {
  local observation record
  [[ $# == 3 && $2 =~ ^[a-f0-9]{32}$ ]] || return 1
  cka_cert_state_expected "$1" >/dev/null || return 1
  observation=$(jq -ces 'select(length==1) | .[0] | select(type=="object" and
    ((.presence=="absent" and keys==["presence"]) or
     (.presence=="present" and keys==["presence","record"])))' <<< "$3") || return 1
  if [[ $(jq -r .presence <<< "$observation") == present ]]; then
    record=$(cka_cert_process_payload "$1" "$2" process "$(jq -c .record <<< "$observation")") || return 1
    jq -cnS --argjson record "$record" '{presence:"present",record:$record}'
  else printf '%s\n' '{"presence":"absent"}'; fi
}

# Shape, expected predecessor and stable operation metadata are not transition permission.
cka_cert_decision_proposal() {
  local expected next
  [[ $# == 4 ]] || return 1
  expected=$(cka_cert_decision_observation "$1" "$2" "$3") || return 1
  next=$(cka_cert_process_payload "$1" "$2" process "$4") || return 1
  jq -cnSe --argjson expected "$expected" --argjson next "$next" '
    select($expected.presence=="absent" or
      ($expected.record!=$next and $expected.record.coordinator==$next.coordinator and
       $expected.record.timeout_seconds==$next.timeout_seconds)) |
    {schema:1,identity:$next.identity,operation_id:$next.operation_id,expected:$expected,next:$next}'
}

# Classifies a supplied observation only: no file access, durability claim or retry.
cka_cert_decision_classify() {
  local proposal observed
  [[ $# == 5 ]] || return 1
  proposal=$(cka_cert_decision_proposal "$1" "$2" "$3" "$4") || return 1
  observed=$(cka_cert_decision_observation "$1" "$2" "$5") || return 1
  jq -nr --argjson proposal "$proposal" --argjson observed "$observed" '
    if $observed=={presence:"present",record:$proposal.next} then "successor"
    elif $observed==$proposal.expected then "predecessor"
    elif $observed.presence=="absent" then "missing"
    else "conflict" end'
}

# Complete decision publication protocol; no lifecycle or certificate activation.
# Called only inside the dedicated, deadline-bounded executor retaining FD8 and FD9.
cka_cert_decision_actual() {
  local record path=/var/lib/cka-certificate-transaction/process.json
  [[ $# == 2 ]] || return 1
  if [[ ! -e $path && ! -L $path ]]; then
    cka_cert_decision_observation "$1" "$2" '{"presence":"absent"}'
  else
    cka_cert_state_file "$path" || return 1
    record=$(cka_cert_process_payload "$1" "$2" process "$(cat -- "$path")") || return 1
    jq -cnS --argjson record "$record" '{presence:"present",record:$record}'
  fi
}

# This predicate never adopts ordinary CONTROL_OWNER. The fixed bootstrap is
# owner -> timeout -> clean Bash executor; every mutating descendant retains 8/9.
cka_cert_decision_executor() {
  local mode request owner owner_start parent parent_start identity operation
  local expected next proposal control state observed classification temporary
  local root=/var/lib/cka-certificate-transaction
  [[ $# == 2 && ( $1 == publish || $1 == reconcile ) &&
     -z ${CKA_CERT_CONTROL_OWNER:-} && -z ${CKA_CERT_CONTROL_DELEGATED:-} ]] || return 1
  mode=$1; request=$2
  jq -es 'length==1 and (.[0] | type=="object" and keys==["control","owner","proposal","state"] and
    (.owner|type=="object" and keys==["pid","start_time"] and
      (.pid|type=="number" and floor==. and .>0) and
      (.start_time|type=="string" and test("^[0-9]+$"))) and
    (.control|type=="string" and test("^[0-9]+:[0-9]+$")) and
    (.state|type=="string" and test("^[0-9]+:[0-9]+$")))' <<< "$request" >/dev/null || return 1
  owner=$(jq -er .owner.pid <<< "$request") || return 1
  owner_start=$(jq -er .owner.start_time <<< "$request") || return 1
  [[ $owner != "$BASHPID" ]] || return 1
  cka_cert_process_stat "$BASHPID" || return 1; parent=$CKA_CERT_PROC_PPID
  cka_cert_process_stat "$parent" || return 1; parent_start=$CKA_CERT_PROC_START
  [[ $CKA_CERT_PROC_PPID == "$owner" ]] || return 1
  cka_cert_process_stat "$owner" || return 1
  [[ $CKA_CERT_PROC_START == "$owner_start" ]] || return 1
  proposal=$(jq -ce .proposal <<< "$request") || return 1
  identity=$(jq -ce .identity <<< "$proposal") || return 1
  operation=$(jq -er .operation_id <<< "$proposal") || return 1
  expected=$(jq -ce .expected <<< "$proposal") || return 1
  next=$(jq -ce .next <<< "$proposal") || return 1
  proposal=$(cka_cert_decision_proposal "$identity" "$operation" "$expected" "$next") || return 1
  jq -e --argjson proposal "$proposal" '.proposal==$proposal' <<< "$request" >/dev/null || return 1
  cka_cert_process_check "$identity" "$operation" && cka_cert_state_locked || return 1
  cka_cert_state_file "$root/control.lock" || return 1
  control=$(stat -Lc '%d:%i' -- "/proc/$BASHPID/fd/8") || return 1
  state=$(stat -Lc '%d:%i' -- "/proc/$BASHPID/fd/9") || return 1
  [[ $control == "$(stat -c '%d:%i' -- "$root/control.lock")" ]] || return 1
  jq -e --arg control "$control" --arg state "$state" \
    '.control==$control and .state==$state' <<< "$request" >/dev/null || return 1
  flock -n 8 || return 1
  cka_cert_process_stat "$parent" || return 1
  [[ $CKA_CERT_PROC_START == "$parent_start" && $CKA_CERT_PROC_PPID == "$owner" ]] || return 1
  observed=$(cka_cert_decision_actual "$identity" "$operation") || return 1
  classification=$(cka_cert_decision_classify "$identity" "$operation" "$expected" "$next" "$observed") || return 1
  if [[ $mode == publish ]]; then
    [[ $classification == predecessor ]] || return 1
    temporary=$(mktemp "$root/decision.XXXXXXXX") || return 1
    cka_cert_state_file "$temporary" || return 1
    printf '%s\n' "$next" > "$temporary" && sync -f "$temporary" || return 1
    # All checks/publication remain under the original exclusive description.
    observed=$(cka_cert_decision_actual "$identity" "$operation") || return 1
    [[ $(cka_cert_decision_classify "$identity" "$operation" "$expected" "$next" "$observed") == predecessor ]] || return 1
    if [[ $(jq -r .presence <<< "$expected") == absent ]]; then
      ln -T -- "$temporary" "$root/process.json" && unlink -- "$temporary" || return 1
    else mv -T -- "$temporary" "$root/process.json" || return 1; fi
    sync -f "$root" || return 1
    printf 'reconciliation_required\n'
  else
    if [[ $classification == successor ]]; then
      sync -f "$root/process.json" && sync -f "$root" || return 1
      observed=$(cka_cert_decision_actual "$identity" "$operation") || return 1
      [[ $(cka_cert_decision_classify "$identity" "$operation" "$expected" "$next" "$observed") == successor ]] || return 1
    fi
    printf '%s\n' "$classification"
  fi
}

# Internal owner dispatch. No callbacks, pipe captures or descriptor-dropping wrappers.
cka_cert_decision_dispatch() {
  local mode deadline proposal control state request output duration result snapshot owner_start
  unset CKA_CERT_DECISION_RESULT
  [[ $# == 6 && ( $1 == publish || $1 == reconcile ) &&
     ${CKA_CERT_STATE_OWNS_FD:-0} == 1 ]] || return 1
  mode=$1; deadline=$2
  [[ $mode != reconcile || ${CKA_CERT_DECISION_FRESH_OWNER:-} == "$BASHPID" ]] || return 1
  cka_cert_control_locked "$deadline" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_descriptor || return $?
  cka_cert_run_utility "$deadline" -- flock -n 9 || return $?
  cka_cert_capture "$deadline" read cka_cert_decision_proposal "$3" "$4" "$5" "$6" || return $?
  proposal=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility stat -Lc '%d:%i' -- "/proc/$BASHPID/fd/8" || return $?
  control=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility stat -Lc '%d:%i' -- "/proc/$BASHPID/fd/9" || return $?
  state=$CKA_CERT_CAPTURED
  cka_cert_process_stat "$BASHPID" || return 1; owner_start=$CKA_CERT_PROC_START
  cka_cert_capture "$deadline" utility jq -cn --argjson pid "$BASHPID" --arg ticks "$owner_start" \
    --arg control "$control" --arg state "$state" --argjson proposal "$proposal" \
    '{owner:{pid:$pid,start_time:$ticks},control:$control,state:$state,proposal:$proposal}' || return $?
  request=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility mktemp /var/lib/cka-certificate-transaction/decision-output.XXXXXXXX || return $?
  output=$CKA_CERT_CAPTURED
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$output" || return $?
  cka_cert_deadline_budget "$deadline" || return $?
  duration=$CKA_CERT_DEADLINE_SOFT
  CKA_CERT_CONTROL_DELEGATED=$BASHPID
  if timeout --foreground --kill-after=0.25s "$duration" \
    env -u BASH_ENV -u ENV bash --noprofile --norc -p -c '
      unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED CKA_CERT_CONTROL_DELEGATED
      source /var/lib/cka-certificate-artifacts/observe.sh || exit 1
      source /var/lib/cka-certificate-artifacts/state.sh || exit 1
      source /var/lib/cka-certificate-artifacts/process.sh || exit 1
      CKA_CERT_STATE_OWNS_FD=1
      cka_cert_decision_executor "$@"
    ' cka-certificate-decision "$mode" "$request" > "$output" 2>&1; then result=0; else result=$?; fi
  cka_cert_control_close || return 1
  cka_cert_process_now || return 1
  (( CKA_CERT_PROCESS_NOW < 10#$deadline )) || return 124
  (( result == 0 )) || return "$result"
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$output" || return $?
  if LC_ALL=C IFS= read -r -d '' -n 65537 snapshot < "$output"; then return 1; else [[ $? == 1 ]] || return 1; fi
  case "$mode:$snapshot" in
    publish:$'reconciliation_required\n'|reconcile:$'successor\n'|reconcile:$'predecessor\n'|\
    reconcile:$'missing\n'|reconcile:$'conflict\n') ;;
    *) return 1 ;;
  esac
  cka_cert_deadline_budget "$deadline" || return $?
  CKA_CERT_DECISION_RESULT=${snapshot%$'\n'}
}

cka_cert_decision_publish() {
  unset CKA_CERT_DECISION_RESULT
  [[ $# == 5 ]] || return 1
  cka_cert_decision_dispatch publish "$@"
}

# Fresh FD8 only; this is not fresh FD9 recovery admission. No stale replay.
cka_cert_decision_reconcile() {
  local result CKA_CERT_DECISION_FRESH_OWNER
  unset CKA_CERT_DECISION_RESULT
  [[ $# == 5 && ${CKA_CERT_STATE_OWNS_FD:-0} == 1 &&
     -z ${CKA_CERT_CONTROL_OWNER:-} && ! -L /proc/$BASHPID/fd/8 ]] || return 1
  cka_cert_control_open "$1" || return $?
  CKA_CERT_DECISION_FRESH_OWNER=$BASHPID
  if cka_cert_decision_dispatch reconcile "$@"; then result=0; else result=$?; fi
  if [[ ${CKA_CERT_CONTROL_OWNER:-} == "$BASHPID" ]]; then cka_cert_control_close || return 1; fi
  return "$result"
}

cka_cert_runner_wait_candidate() {
  local child generation result completed
  unset CKA_CERT_WAIT_EXIT
  [[ $# == 1 && $1 =~ ^[1-9][0-9]*$ &&
     ${CKA_CERT_WAIT_GENERATION:-} =~ ^[0-9]+$ ]] || return 1
  child=$1
  [[ ! -o posix && ! -o monitor ]] || return 1
  while :; do
    generation=$CKA_CERT_WAIT_GENERATION
    unset completed
    if wait -p completed "$child"; then result=0; else result=$?; fi
    # Conservatively repeat even if the signal followed a real completion.
    # Non-POSIX explicit wait retains the cached status for this same PID.
    (( generation == CKA_CERT_WAIT_GENERATION )) || continue
    [[ ${completed:-} == "$child" ]] || return 1
    CKA_CERT_WAIT_EXIT=$result
    return 0
  done
}


# Pure runner-record schema validation (Slice A / #2478). No live custody.
# Rejects argv with embedded NUL; ready/admission require child==null;
# birth/entry require a person-shaped child distinct from runner/supervisor.
cka_cert_runner_payload() {
  local identity
  [[ $# == 5 && $2 =~ ^[a-f0-9]{32}$ ]] || return 1
  identity=$(cka_cert_state_expected "$1") || return 1
  jq -ces --argjson identity "$identity" --arg operation "$2" \
    --argjson binding "$3" --arg kind "$4" '
    def pid: type=="number" and floor==. and .>0;
    def person: type=="object" and keys==["pid","start_time"] and
      (.pid|pid) and (.start_time|type=="string" and test("^[0-9]+$"));
    def leader: type=="object" and keys==["pgid","pid","sid","start_time"] and
      ({pid,start_time}|person) and .pid==.pgid and .pid==.sid;
    select(length==1) | .[0] |
    select($binding|type=="object" and keys==["argv","runner","supervisor"] and
      (.runner|person) and (.supervisor|leader) and .runner.pid!=.supervisor.pid and
      (.argv|type=="array" and length>0 and length<=32 and (.[0]|length>0) and
        all(.[]; type=="string" and (explode|index(0)==null)))) |
    select(type=="object" and keys==["argv","child","identity","kind","operation_id",
      "runner","schema","supervisor"]) |
    select(.schema==1 and .identity==$identity and .operation_id==$operation and
      .kind==$kind and .argv==$binding.argv and .runner==$binding.runner and .supervisor==$binding.supervisor) |
    select(if $kind=="ready" or $kind=="admission" then .child==null
      elif $kind=="birth" or $kind=="entry" then (.child|person) and
        .child.pid!=.runner.pid and .child.pid!=.supervisor.pid else false end)
  ' <<< "$5"
}

# Read-only identity evidence. The actual writer separately checks its BASHPID.
cka_cert_runner_live() {
  local binding supervisor runner child expected_start
  [[ $# == 2 ]] || return 1
  binding=$1; child=$2
  supervisor=$(jq -er .supervisor.pid <<< "$binding") || return 1
  runner=$(jq -er .runner.pid <<< "$binding") || return 1
  expected_start=$(jq -er .supervisor.start_time <<< "$binding") || return 1
  cka_cert_process_stat "$supervisor" || return 1
  [[ $CKA_CERT_PROC_START == "$expected_start" && $CKA_CERT_PROC_SID == "$supervisor" &&
     $CKA_CERT_PROC_PGID == "$supervisor" && $CKA_CERT_PROC_STATE != [ZXx] ]] || return 1
  expected_start=$(jq -er .runner.start_time <<< "$binding") || return 1
  cka_cert_process_stat "$runner" || return 1
  [[ $CKA_CERT_PROC_START == "$expected_start" && $CKA_CERT_PROC_PPID == "$supervisor" &&
     $CKA_CERT_PROC_SID == "$supervisor" && $CKA_CERT_PROC_PGID == "$supervisor" &&
     $CKA_CERT_PROC_STATE != [ZXx] ]] || return 1
  if [[ $child != null ]]; then
    expected_start=$(jq -er .start_time <<< "$child") || return 1
    cka_cert_process_stat "$(jq -er .pid <<< "$child")" || return 1
    [[ $CKA_CERT_PROC_START == "$expected_start" && $CKA_CERT_PROC_PPID == "$runner" &&
       $CKA_CERT_PROC_SID == "$supervisor" && $CKA_CERT_PROC_PGID == "$supervisor" &&
       $CKA_CERT_PROC_STATE != [ZXx] ]] || return 1
  fi
}

cka_cert_runner_read() {
  local path payload
  [[ $# == 4 && ( $4 == ready || $4 == admission || $4 == birth || $4 == entry ) ]] || return 1
  cka_cert_process_check "$1" "$2" || return 1
  path=/var/lib/cka-certificate-transaction/runner-$4.json
  cka_cert_state_file "$path" || return 1
  payload=$(cat -- "$path") || return 1
  cka_cert_runner_payload "$1" "$2" "$3" "$4" "$payload"
}

# Evidence records are exclusive, never an alternate lifecycle authority.
# Direct invocation only; all utility children drop FD8 while this actor retains it.
cka_cert_runner_write() {
  local deadline identity operation binding kind payload target temporary actor child
  [[ $# == 6 && ${CKA_CERT_STATE_OWNS_FD:-0} == 1 ]] || return 1
  deadline=$1; identity=$2; operation=$3; binding=$4; kind=$5
  cka_cert_capture "$deadline" read cka_cert_runner_payload "$identity" "$operation" "$binding" "$kind" "$6" || return $?
  payload=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -cr .child <<< "$payload" || return $?
  child=$CKA_CERT_CAPTURED
  case $kind in ready) actor=.runner.pid ;; admission) actor=.supervisor.pid ;; *) actor=.child.pid ;; esac
  cka_cert_capture "$deadline" utility jq -er "$actor" <<< "$payload" || return $?
  [[ $BASHPID == "$CKA_CERT_CAPTURED" ]] || return 1
  cka_cert_run_read_helper "$deadline" cka_cert_runner_live "$binding" "$child" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_process_check "$identity" "$operation" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_descriptor || return $?
  cka_cert_run_utility "$deadline" -- flock -n 9 || return $?
  target=/var/lib/cka-certificate-transaction/runner-$kind.json
  [[ ! -e $target && ! -L $target ]] || return 1
  cka_cert_capture "$deadline" utility mktemp /var/lib/cka-certificate-transaction/runner.XXXXXXXX || return $?
  temporary=$CKA_CERT_CAPTURED
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$temporary" || return $?
  cka_cert_deadline_budget "$deadline" || return $?
  printf '%s\n' "$payload" > "$temporary" || return 1
  cka_cert_run_utility "$deadline" -- sync -f "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- ln -T -- "$temporary" "$target" || return $?
  cka_cert_run_utility "$deadline" -- unlink -- "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- sync -f /var/lib/cka-certificate-transaction || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_runner_read "$identity" "$operation" "$binding" "$kind" >/dev/null
}

# The caller retains freshly acquired FD8. A cancelled or changed state refuses launch.
cka_cert_runner_permission() {
  local record
  [[ $# == 4 && ( $4 == supervisor_ready || $4 == command_launch_committed ) ]] || return 1
  cka_cert_runner_live "$3" null || return 1
  record=$(cka_cert_process_read "$1" "$2") || return 1
  jq -e --argjson binding "$3" --arg stage "$4" \
    '.stage==$stage and .supervisor==$binding.supervisor and .cancel_ack==false and .cause=="none"' \
    <<< "$record" >/dev/null || return 1
  cka_cert_process_cancel_read "$1" "$2" && [[ $CKA_CERT_PROCESS_CANCEL == 0 ]]
}

# Constructor uses the invocation's original binding, never adopts recorded argv.
cka_cert_runner_record() {
  [[ $# == 6 ]] || return 1
  cka_cert_capture "$1" utility jq -cn --argjson identity "$2" --arg operation "$3" \
    --argjson binding "$4" --arg kind "$5" --argjson child "$6" \
    '$binding+{schema:1,identity:$identity,operation_id:$operation,kind:$kind,child:$child}'
}

# Retrospective validation uses preserved live evidence, not /proc after reaping.
cka_cert_runner_evidence() {
  local birth entry
  [[ $# == 3 ]] || return 1
  birth=$(cka_cert_runner_read "$1" "$2" "$3" birth) || return 1
  entry=$(cka_cert_runner_read "$1" "$2" "$3" entry) || return 1
  jq -ce --argjson birth "$birth" 'select(.==($birth|.kind="entry")) | .child' <<< "$entry"
}

# Only this composite reader supplies accepted command evidence to supervision.
# Expected binding (including argv) comes from the original admitted invocation.
cka_cert_runner_receipt_read() {
  local child receipt supervisor runner
  [[ $# == 3 ]] || return 1
  cka_cert_runner_read "$1" "$2" "$3" ready >/dev/null || return 1
  cka_cert_runner_read "$1" "$2" "$3" admission >/dev/null || return 1
  child=$(cka_cert_runner_evidence "$1" "$2" "$3") || return 1
  supervisor=$(jq -ce .supervisor <<< "$3") || return 1
  runner=$(jq -ce .runner <<< "$3") || return 1
  receipt=$(cka_cert_supervisor_receipt_read "$1" "$2" "$supervisor" "$runner") || return 1
  jq -ce --argjson child "$child" 'select(.child_pid==$child.pid)' <<< "$receipt"
}

# Fixed clean-Bash entrypoint; reaching this function occurs AFTER its exec.
# Entry proves this wrapper began, never that the reviewed nested argv executed.
cka_cert_runner_entry() {
  local deadline identity operation binding birth child argv result
  [[ $# -ge 5 && ${BASH_VERSINFO[0]} == 5 && ${BASH_VERSINFO[1]} == 2 ]] || return 1
  deadline=$1; identity=$2; operation=$3; binding=$4; shift 4
  cka_cert_capture "$deadline" utility jq -cn --args '$ARGS.positional' -- "$@" || return $?
  argv=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -ce --argjson argv "$argv" \
    'select(.argv==$argv)' <<< "$binding" || return $?
  cka_cert_capture "$deadline" read cka_cert_runner_read "$identity" "$operation" "$binding" birth || return $?
  birth=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -ce .child <<< "$birth" || return $?
  child=$CKA_CERT_CAPTURED
  cka_cert_runner_record "$deadline" "$identity" "$operation" "$binding" entry "$child" || return $?
  cka_cert_runner_write "$deadline" "$identity" "$operation" "$binding" entry "$CKA_CERT_CAPTURED" || return $?
  cka_cert_deadline_budget "$deadline" || return $?
  if "$@"; then result=0; else result=$?; fi
  return "$result"
}

# Dedicated runner bootstrap, invoked only by the supervisor launch function.
cka_cert_runner_body() {
  local deadline identity operation supervisor argv binding runner child child_start result evidence payload actual_argv
  [[ $# -ge 6 && ${BASH_VERSINFO[0]} == 5 && ${BASH_VERSINFO[1]} == 2 ]] || return 1
  deadline=$1; identity=$2; operation=$3; supervisor=$4; argv=$5; shift 5
  local -a command=("$@")
  set +o posix; set +m
  CKA_CERT_WAIT_GENERATION=0
  trap 'CKA_CERT_WAIT_GENERATION=$((CKA_CERT_WAIT_GENERATION + 1))' HUP INT QUIT TERM
  cka_cert_capture "$deadline" utility jq -cn --args '$ARGS.positional' -- "${command[@]}" || return $?
  actual_argv=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -ce --argjson actual "$actual_argv" \
    'select(.==$actual)' <<< "$argv" || return $?
  cka_cert_process_stat "$BASHPID" || return 1
  cka_cert_capture "$deadline" utility jq -cn --argjson pid "$BASHPID" --arg start "$CKA_CERT_PROC_START" \
    --argjson supervisor "$supervisor" --argjson argv "$argv" \
    '{supervisor:$supervisor,runner:{pid:$pid,start_time:$start},argv:$argv}' || return $?
  binding=$CKA_CERT_CAPTURED
  cka_cert_runner_record "$deadline" "$identity" "$operation" "$binding" ready null || return $?
  cka_cert_runner_write "$deadline" "$identity" "$operation" "$binding" ready "$CKA_CERT_CAPTURED" || return $?
  while [[ ! -e /var/lib/cka-certificate-transaction/runner-admission.json &&
           ! -L /var/lib/cka-certificate-transaction/runner-admission.json ]]; do
    (( CKA_CERT_WAIT_GENERATION == 0 )) || return 1
    cka_cert_run_read_helper "$deadline" cka_cert_runner_live "$binding" null || return $?
  done
  until cka_cert_control_open "$deadline"; do
    (( CKA_CERT_WAIT_GENERATION == 0 )) || return 1
    cka_cert_deadline_budget "$deadline" || return $?
    cka_cert_run_read_helper "$deadline" cka_cert_runner_live "$binding" null || return $?
  done
  # Visibility is not durability. Reconcile immutable admission under fresh FD8.
  if ! cka_cert_run_read_helper "$deadline" cka_cert_runner_read "$identity" "$operation" "$binding" admission >/dev/null ||
     ! cka_cert_run_utility "$deadline" -- sync -f /var/lib/cka-certificate-transaction/runner-admission.json ||
     ! cka_cert_run_utility "$deadline" -- sync -f /var/lib/cka-certificate-transaction ||
     ! cka_cert_run_read_helper "$deadline" cka_cert_runner_read "$identity" "$operation" "$binding" admission >/dev/null; then
    cka_cert_control_close; return 1
  fi
  if ! cka_cert_run_read_helper "$deadline" cka_cert_runner_permission "$identity" "$operation" "$binding" command_launch_committed ||
     (( CKA_CERT_WAIT_GENERATION != 0 )); then cka_cert_control_close; return 1; fi
  (
    exec 8>&-
    unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED CKA_CERT_CONTROL_DELEGATED
    trap - HUP INT QUIT TERM
    cka_cert_process_stat "$BASHPID" || exit 1
    child_start=$CKA_CERT_PROC_START
    cka_cert_capture "$deadline" utility jq -cn --argjson pid "$BASHPID" --arg start "$child_start" \
      '{pid:$pid,start_time:$start}' || exit 1
    child=$CKA_CERT_CAPTURED
    cka_cert_runner_record "$deadline" "$identity" "$operation" "$binding" birth "$child" || exit 1
    cka_cert_runner_write "$deadline" "$identity" "$operation" "$binding" birth "$CKA_CERT_CAPTURED" || exit 1
    exec env -u BASH_ENV -u ENV bash --noprofile --norc -p -c '
      source /var/lib/cka-certificate-artifacts/observe.sh || exit 1
      source /var/lib/cka-certificate-artifacts/state.sh || exit 1
      source /var/lib/cka-certificate-artifacts/process.sh || exit 1
      CKA_CERT_STATE_OWNS_FD=1
      cka_cert_runner_entry "$@"
    ' cka-certificate-command "$deadline" "$identity" "$operation" "$binding" "${command[@]}"
  ) &
  child=$!
  cka_cert_control_close || return 1
  cka_cert_runner_wait_candidate "$child" || return 1
  result=$CKA_CERT_WAIT_EXIT
  cka_cert_capture "$deadline" read cka_cert_runner_evidence "$identity" "$operation" "$binding" || return $?
  evidence=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -er .pid <<< "$evidence" || return $?
  [[ $CKA_CERT_CAPTURED == "$child" ]] || return 1
  cka_cert_capture "$deadline" utility jq -ce .runner <<< "$binding" || return $?
  runner=$CKA_CERT_CAPTURED
  cka_cert_capture "$deadline" utility jq -cn --argjson identity "$identity" --arg operation "$operation" \
    --argjson supervisor "$supervisor" --argjson runner "$runner" --argjson child "$child" --argjson result "$result" \
    '{schema:1,identity:$identity,operation_id:$operation,supervisor:$supervisor,runner:$runner,child_pid:$child,exit_code:$result}' || return $?
  payload=$CKA_CERT_CAPTURED
  cka_cert_supervisor_receipt_write "$deadline" "$identity" "$operation" "$supervisor" "$runner" "$payload" || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_runner_receipt_read "$identity" "$operation" "$binding" >/dev/null
}

# Pre-runner read-only check, before a runner identity can exist.
cka_cert_runner_before() {
  local observed
  [[ $# == 4 ]] || return 1
  cka_cert_process_check "$1" "$2" || return 1
  observed=$(cka_cert_process_read "$1" "$2") || return 1
  jq -e --argjson before "$4" --argjson supervisor "$3" \
    '.==$before and .supervisor==$supervisor and .stage=="supervisor_ready" and
      .cancel_ack==false and .cause=="none"' <<< "$observed" >/dev/null || return 1
  cka_cert_process_cancel_read "$1" "$2" && [[ $CKA_CERT_PROCESS_CANCEL == 0 ]]
}
