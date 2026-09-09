# Internal read-only Bash library. Sourcing defines functions only.
# Pass inputs explicitly: no ambient kubeconfig, context or CRI endpoint fallback.
# Requires Bash, jq, timeout, OpenSSL 3.0, kubectl and a crictl 1.35 executable.

cka_cert_obs_error() {
  printf 'Certificate observation refused: %s\n' "$*" >&2
  return 1
}

cka_cert_obs_file() {
  [[ $# == 1 && -f $1 && -r $1 && ! -L $1 ]] || {
    cka_cert_obs_error 'Expected a readable regular non-symlink file'; return 1;
  }
}

# Full lowercase hex IDs are the intended containerd fixture contract, not all CRI implementations.
cka_cert_obs_cri_json() {
  [[ $# == 2 && -n $1 && $2 == unix:///* ]] || {
    cka_cert_obs_error 'Supply CRI_BIN and a known Linux CRI_ENDPOINT'; return 1;
  }
  local version response
  version=$(timeout --kill-after=5s 10s "$1" --version) || return 1
  [[ $version =~ ^crictl\ version\ v1\.35\.[0-9]+$ ]] || {
    cka_cert_obs_error 'Expected crictl 1.35'; return 1;
  }
  response=$(timeout --kill-after=5s 20s "$1" --runtime-endpoint "$2" --timeout=10s \
    ps -a --name kube-apiserver -o json) || return 1
  jq -ce -s '
    if length==1 and (.[0] | type=="object") and
       (.[0].containers | type=="array") and
       all(.[0].containers[];
         type=="object" and
         (.id | type=="string" and test("^[a-f0-9]{64}$")) and
         (.metadata | type=="object") and .metadata.name=="kube-apiserver" and
         (.labels | type=="object") and .labels["io.kubernetes.pod.namespace"]=="kube-system" and
         (.state=="CONTAINER_CREATED" or .state=="CONTAINER_RUNNING" or
          .state=="CONTAINER_EXITED" or .state=="CONTAINER_UNKNOWN")) and
       ((.[0].containers | map(.id) | length)==(.[0].containers | map(.id) | unique | length))
    then .[0] else error("Invalid CRI shape, component, state or identity") end
  ' <<< "$response" || return 1
}

# Prints a JSON array. [] is valid absence; no ordering or timestamp inference.
cka_cert_obs_running_ids() {
  local response
  response=$(cka_cert_obs_cri_json "$@") || return 1
  jq -ce '[.containers[] | select(.state=="CONTAINER_RUNNING") | .id]' <<< "$response" || return 1
}

cka_cert_obs_fingerprint() {
  [[ $# == 1 ]] && cka_cert_obs_file "$1" || return 1
  timeout --kill-after=5s 10s openssl x509 -in "$1" -noout -fingerprint -sha256 || return 1
}

# Prints OpenSSL issuer/subject/SAN text, not a canonical semantic SAN ordering.
cka_cert_obs_identity() {
  [[ $# == 1 ]] && cka_cert_obs_file "$1" || return 1
  local identity
  identity=$(timeout --kill-after=5s 10s openssl x509 -in "$1" -noout \
    -issuer -subject -ext subjectAltName) || return 1
  [[ $identity == *'X509v3 Subject Alternative Name:'* ]] || {
    cka_cert_obs_error 'Certificate has no observed SAN extension'; return 1;
  }
  printf '%s\n' "$identity"
}

# Compares only derived public-key hashes; private key bytes never enter stdout.
cka_cert_obs_pair() {
  [[ $# == 2 ]] && cka_cert_obs_file "$1" && cka_cert_obs_file "$2" || return 1
  local certificate_public key_public
  certificate_public=$(
    set -o pipefail
    timeout --kill-after=5s 10s openssl x509 -in "$1" -pubkey -noout |
      timeout --kill-after=5s 10s openssl pkey -pubin -outform DER |
      timeout --kill-after=5s 10s openssl dgst -sha256
  ) || return 1
  key_public=$(
    set -o pipefail
    timeout --kill-after=5s 10s openssl pkey -in "$2" -passin pass: -pubout -outform DER |
      timeout --kill-after=5s 10s openssl dgst -sha256
  ) || return 1
  [[ -n $certificate_public && $certificate_public == "$key_public" ]] || {
    cka_cert_obs_error 'Certificate/private-key pair differs'; return 1;
  }
  printf '%s\n' "$certificate_public"
}

# Arguments: CA certificate, serving certificate. No system CA directories/store.
cka_cert_obs_chain() {
  [[ $# == 2 ]] && cka_cert_obs_file "$1" && cka_cert_obs_file "$2" || return 1
  timeout --kill-after=5s 10s openssl verify -no-CApath -no-CAstore -CAfile "$1" "$2" || return 1
}

# Arguments: trusted CA file, literal IP, port. Prints the trusted leaf fingerprint.
cka_cert_obs_served_fingerprint() {
  [[ $# == 3 ]] && cka_cert_obs_file "$1" || return 1
  local ip=$2 port=$3 address
  [[ $ip =~ ^[0-9a-fA-F:.]+$ && $port =~ ^[0-9]{1,5}$ ]] || return 1
  (( 10#$port > 0 && 10#$port <= 65535 )) || return 1
  address="$ip:$port"
  [[ $ip != *:* ]] || address="[$ip]:$port"
  (
    set -o pipefail
    timeout --kill-after=5s 20s openssl s_client -connect "$address" \
      -verify_ip "$ip" -verify_return_error -no-CApath -no-CAstore -CAfile "$1" \
      -showcerts </dev/null |
      timeout --kill-after=5s 20s openssl x509 -noout -fingerprint -sha256
  ) || return 1
}

# Arguments: kubeconfig, context, expected system UID, marker namespace/name/UID/value.
# Read-only: returns public JSON evidence only after every expected value matches.
cka_cert_obs_api_identity() {
  [[ $# == 7 ]] && cka_cert_obs_file "$1" || return 1
  local context=$2 system_uid=$3 namespace=$4 name=$5 marker_uid=$6 value=$7
  local ready observed_uid marker
  [[ -n $context && -n $system_uid && -n $marker_uid && -n $value ]] || return 1
  [[ $1 == /* && $namespace =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ &&
     $name =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ]] || return 1
  local -a api=(timeout --kill-after=5s 25s kubectl --kubeconfig "$1" \
    --context "$context" --request-timeout=15s)
  ready=$("${api[@]}" get --raw=/readyz) || return 1
  [[ $ready == ok ]] || { cka_cert_obs_error 'API readiness not confirmed'; return 1; }
  observed_uid=$("${api[@]}" get namespace kube-system -o jsonpath='{.metadata.uid}') || return 1
  [[ $observed_uid == "$system_uid" ]] || { cka_cert_obs_error 'System UID differs'; return 1; }
  marker=$("${api[@]}" -n "$namespace" get configmap "$name" -o json) || return 1
  jq -ce -s --arg uid "$marker_uid" --arg value "$value" --arg system "$system_uid" \
    --arg namespace "$namespace" --arg name "$name" '
    if length==1 and (.[0] | type=="object") and .[0].kind=="ConfigMap" and
       .[0].metadata.namespace==$namespace and .[0].metadata.name==$name and
       .[0].metadata.uid==$uid and .[0].data.value==$value
    then {ready:true,system_namespace_uid:$system,marker_uid:$uid,marker_value:$value}
    else error("Marker identity or value differs") end
  ' <<< "$marker" || return 1
}
