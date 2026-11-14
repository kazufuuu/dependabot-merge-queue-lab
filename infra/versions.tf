terraform {
  required_version = "= 1.16.5"

  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.8.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.3.0"
    }
  }
}
