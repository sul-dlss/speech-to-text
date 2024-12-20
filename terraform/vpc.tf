/*
 
TODO: configure a network that works! I'm relying on a default that was created in the AWS web interface.

resource "aws_security_group" "security_group" {
  name = var.project_name
  vpc_id = aws_vpc.vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_vpc" "vpc" {
  cidr_block = "10.1.0.0/16"
}

resource "aws_subnet" "subnet" {
  vpc_id     = aws_vpc.vpc.id
  cidr_block = "10.1.1.0/24"
  map_public_ip_on_launch = true
}

*/


