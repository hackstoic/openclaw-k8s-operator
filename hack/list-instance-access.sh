#!/usr/bin/env bash
set -euo pipefail

namespace="${1:-openclaw}"
selector="${2:-}"

jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.networking.ingress.hosts[*]}{.host}{","}{end}{"\t"}{.status.managedResources.gatewayTokenSecret}{"\n"}{end}'

kubectl_args=(-n "$namespace" get openclawinstances)
if [[ -n "$selector" ]]; then
	kubectl_args+=(-l "$selector")
fi
kubectl_args+=(-o "jsonpath=${jsonpath}")

rows="$(kubectl "${kubectl_args[@]}")"

printf 'INSTANCE\tDOMAINS\tGATEWAY_TOKEN\n'
if [[ -z "$rows" ]]; then
	exit 0
fi

while IFS=$'\t' read -r name domains secret; do
	[[ -z "$name" ]] && continue

	domains="${domains%,}"
	token=""
	if [[ -n "$secret" ]]; then
		encoded="$(kubectl -n "$namespace" get secret "$secret" -o jsonpath='{.data.token}' 2>/dev/null || true)"
		if [[ -n "$encoded" ]]; then
			token="$(python3 -c 'import base64, sys; data = sys.stdin.read().strip(); print(base64.b64decode(data).decode() if data else "", end="")' <<<"$encoded")"
		fi
	fi

	printf '%s\t%s\t%s\n' "$name" "${domains:--}" "$token"
done <<<"$rows"
