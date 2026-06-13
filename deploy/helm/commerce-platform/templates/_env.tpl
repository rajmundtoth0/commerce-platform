{{/*
Container env shared by the Deployment and the migration Job.
ConfigMap supplies non-secret config; the Postgres password comes from a Secret
and is referenced by the DSN via Kubernetes dependent-variable expansion.
*/}}
{{- define "commerce-platform.envVars" -}}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "commerce-platform.secretName" . }}
      key: {{ .Values.postgres.existingSecretPasswordKey }}
- name: POSTGRES_DSN
  value: {{ include "commerce-platform.postgresDsn" . | quote }}
- name: REDIS_URL
  value: {{ .Values.redis.url | quote }}
{{- end }}
