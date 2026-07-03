-- One Postgres instance, one database per owning service. This models
-- "database per service" (each service connects only to its own database and
-- has no access to the others') while keeping local infra to a single container.
-- In production each of these would typically be a separate managed instance.
CREATE DATABASE auth;
CREATE DATABASE orders;
CREATE DATABASE backoffice;
CREATE DATABASE status;
