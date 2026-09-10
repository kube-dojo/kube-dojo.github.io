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

# Invoke directly in the admitted runner, not in a timeout-created Bash child.
# This proves writer identity/custody only; the runner must supply real wait evidence.
cka_cert_supervisor_receipt_write() {
  local payload temporary runner_pid runner_start supervisor_pid supervisor_start
  [[ $# == 5 ]] || return 1
  payload=$(cka_cert_supervisor_receipt_payload "$1" "$2" "$3" "$4" "$5") || return 1
  cka_cert_process_check "$1" "$2" && cka_cert_state_locked || return 1
  runner_pid=$(jq -er .pid <<< "$4") || return 1
  runner_start=$(jq -er .start_time <<< "$4") || return 1
  supervisor_pid=$(jq -er .pid <<< "$3") || return 1
  supervisor_start=$(jq -er .start_time <<< "$3") || return 1
  [[ $BASHPID == "$runner_pid" ]] || return 1
  cka_cert_process_stat "$supervisor_pid" || return 1
  [[ $CKA_CERT_PROC_START == "$supervisor_start" && $CKA_CERT_PROC_PGID == "$supervisor_pid" &&
     $CKA_CERT_PROC_SID == "$supervisor_pid" ]] || return 1
  cka_cert_process_stat "$BASHPID" || return 1
  [[ $CKA_CERT_PROC_START == "$runner_start" && $CKA_CERT_PROC_PPID == "$supervisor_pid" &&
     $CKA_CERT_PROC_PGID == "$supervisor_pid" && $CKA_CERT_PROC_SID == "$supervisor_pid" ]] || return 1
  [[ ! -e /var/lib/cka-certificate-transaction/command.json &&
     ! -L /var/lib/cka-certificate-transaction/command.json ]] || return 1
  temporary=$(mktemp /var/lib/cka-certificate-transaction/command.XXXXXXXX) || return 1
  cka_cert_state_file "$temporary" || return 1
  printf '%s\n' "$payload" > "$temporary" || return 1
  sync -f "$temporary" || return 1
  # Exclusive link creation also refuses a destination appearing after the check.
  ln -T -- "$temporary" /var/lib/cka-certificate-transaction/command.json || return 1
  # A crash before this unlink leaves two links and therefore a refused receipt.
  unlink -- "$temporary" || return 1
  sync -f /var/lib/cka-certificate-transaction || return 1
  cka_cert_supervisor_receipt_read "$1" "$2" "$3" "$4" >/dev/null
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
    cka_cert_process_check|cka_cert_process_read|cka_cert_process_payload|\
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
  temporary=$(cka_cert_run_utility "$deadline" -- mktemp /var/lib/cka-certificate-transaction/control.XXXXXXXX) || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_file "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- sync -f "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- ln -T -- "$temporary" /var/lib/cka-certificate-transaction/control.lock || return $?
  cka_cert_run_utility "$deadline" -- unlink -- "$temporary" || return $?
  cka_cert_run_utility "$deadline" -- sync -f /var/lib/cka-certificate-transaction || return $?
  cka_cert_run_read_helper "$deadline" cka_cert_state_file /var/lib/cka-certificate-transaction/control.lock
}

cka_cert_control_descriptor() {
  local descriptor inode path
  [[ $# == 1 && ${CKA_CERT_CONTROL_OWNER:-} == "$BASHPID" && -L /proc/$BASHPID/fd/8 ]] || return 1
  path=/proc/$BASHPID/fd/8
  cka_cert_run_read_helper "$1" cka_cert_state_file /var/lib/cka-certificate-transaction/control.lock || return $?
  descriptor=$(cka_cert_run_utility "$1" -- stat -Lc '%d:%i:%u:%a:%h' -- "$path") || return $?
  inode=$(cka_cert_run_utility "$1" -- stat -c '%d:%i:%u:%a:%h' -- /var/lib/cka-certificate-transaction/control.lock) || return $?
  [[ $descriptor == "$inode" && $inode == *:0:600:1 ]]
}

# The only acquisition wrapper retaining FD8; never accepts arbitrary commands.
cka_cert_control_acquire() {
  local deadline duration result
  [[ $# == 1 && ${CKA_CERT_CONTROL_OWNER:-} == "$BASHPID" && -L /proc/$BASHPID/fd/8 ]] || return 1
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
  unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED
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
  unset CKA_CERT_CONTROL_OWNER CKA_CERT_CONTROL_LOCKED
}
