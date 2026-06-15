{{- define "cp.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "cp.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: commerce-platform
{{- end }}

{{- define "cp.jwtSecretName" -}}
{{- if .Values.global.jwtExistingSecret }}{{ .Values.global.jwtExistingSecret }}{{ else }}{{ .Release.Name }}-jwt{{ end }}
{{- end }}

{{- define "cp.pgSecretName" -}}
{{- if .Values.global.postgres.existingSecret }}{{ .Values.global.postgres.existingSecret }}{{ else }}{{ .Release.Name }}-postgres{{ end }}
{{- end }}

{{/* Assemble a Postgres DSN for a given database name. Password comes from env
     POSTGRES_PASSWORD via Kubernetes dependent-variable expansion. */}}
{{- define "cp.dsn" -}}
{{- $db := index . 0 -}}{{- $root := index . 1 -}}
{{- printf "postgresql+asyncpg://%s:$(POSTGRES_PASSWORD)@%s:%v/%s" $root.Values.global.postgres.user $root.Values.global.postgres.host $root.Values.global.postgres.port $db -}}
{{- end }}

{{/* Shared env for every Python service. `svc` is the service config dict, root is . */}}
{{- define "cp.env" -}}
{{- $svc := index . 0 -}}{{- $root := index . 1 -}}
- name: APP_ENV
  value: production
- name: LOG_LEVEL
  value: INFO
- name: JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "cp.jwtSecretName" $root }}
      key: JWT_SECRET
- name: VALKEY_URL
  value: {{ $root.Values.global.valkey.url | quote }}
- name: CELERY_BROKER_URL
  value: {{ $root.Values.global.valkey.brokerUrl | quote }}
- name: CELERY_RESULT_BACKEND
  value: {{ $root.Values.global.valkey.resultBackend | quote }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ $root.Values.global.otelEndpoint | quote }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "cp.pgSecretName" $root }}
      key: {{ $root.Values.global.postgres.existingSecretPasswordKey }}
{{- if $svc.db }}
- name: POSTGRES_DSN
  value: {{ include "cp.dsn" (list $svc.db $root) | quote }}
{{- end }}
{{- range $envName, $db := $svc.dbEnvs }}
- name: {{ $envName }}
  value: {{ include "cp.dsn" (list $db $root) | quote }}
{{- end }}
{{- range $k, $v := $svc.extraEnv }}
- name: {{ $k }}
  value: {{ $v | quote }}
{{- end }}
{{- end }}
