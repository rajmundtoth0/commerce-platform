terraform {
  required_version = ">= 1.6"
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.43"
    }
  }

  # Recommended: store state in Scaleway Object Storage (S3-compatible).
  # Create the bucket first, then uncomment and `terraform init -migrate-state`.
  # backend "s3" {
  #   bucket                      = "commerce-tfstate"
  #   key                         = "stg/terraform.tfstate"
  #   region                      = "fr-par"
  #   endpoints                   = { s3 = "https://s3.fr-par.scw.cloud" }
  #   skip_credentials_validation = true
  #   skip_region_validation      = true
  #   skip_requesting_account_id  = true
  # }
}

# Credentials come from the environment: SCW_ACCESS_KEY, SCW_SECRET_KEY.
provider "scaleway" {
  region     = var.region
  zone       = var.zone
  project_id = var.project_id
}
