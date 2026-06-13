{{/* Expand the name of the chart. */}}
{{- define "commerce-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Fully qualified app name. */}}
{{- define "commerce-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "commerce-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "commerce-platform.labels" -}}
helm.sh/chart: {{ include "commerce-platform.chart" . }}
{{ include "commerce-platform.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "commerce-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "commerce-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "commerce-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "commerce-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* Name of the secret that holds the Postgres password. */}}
{{- define "commerce-platform.secretName" -}}
{{- if .Values.postgres.existingSecret }}
{{- .Values.postgres.existingSecret }}
{{- else }}
{{- include "commerce-platform.fullname" . }}
{{- end }}
{{- end }}

{{/* Assembled Postgres DSN when an explicit one is not provided. */}}
{{- define "commerce-platform.postgresDsn" -}}
{{- if .Values.postgres.dsn }}
{{- .Values.postgres.dsn }}
{{- else }}
{{- printf "postgresql+asyncpg://%s:$(POSTGRES_PASSWORD)@%s:%v/%s" .Values.postgres.user .Values.postgres.host .Values.postgres.port .Values.postgres.database }}
{{- end }}
{{- end }}
