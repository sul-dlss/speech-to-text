provider "aws" {
  region  = "us-east-1"

  default_tags {
    tags = {
      environment = "qa"
      project     = "speech_to_text"
      terraform   = "true"
    }
  }
}
