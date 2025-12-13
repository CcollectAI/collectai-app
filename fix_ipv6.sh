set -euo pipefail
REGION="eu-north-1"
VPC_ID="vpc-0c80255923aef3e62"               # fill
SUBNET_ID="subnet-065f1a292a41a4d0f"         # fill
ROUTE_TABLE_ID="rtb-02ea8933790c47020"       # fill
ENI_ID="eni-006cbfa9ba2f53340"               # fill

aws configure set default.region "$REGION"

# Ensure VPC has IPv6
aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --query "Vpcs[0].Ipv6CidrBlockAssociationSet[?Ipv6CidrBlockState.State=='associated']|length(@)" --output text | grep -q 1 || \
aws ec2 associate-vpc-cidr-block --vpc-id "$VPC_ID" --amazon-provided-ipv6-cidr-block >/dev/null

VPC_CIDR6="$(aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --query "Vpcs[0].Ipv6CidrBlockAssociationSet[?Ipv6CidrBlockState.State=='associated'][0].Ipv6CidrBlock" --output text)"

# Ensure subnet has /64
aws ec2 describe-subnets --subnet-ids "$SUBNET_ID" --query "Subnets[0].Ipv6CidrBlockAssociationSet[?Ipv6CidrBlockState.State=='associated']|length(@)" --output text | grep -q 1 || {
  SUBNET_CIDR6="$(python3 - <<PY
import ipaddress; print(list(ipaddress.IPv6Network("$VPC_CIDR6").subnets(new_prefix=64))[0])
PY
)"
  aws ec2 associate-subnet-cidr-block --subnet-id "$SUBNET_ID" --ipv6-cidr-block "$SUBNET_CIDR6" >/dev/null
}

# Auto-assign v6 on subnet
aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_ID" --assign-ipv6-address-on-creation >/dev/null || true

# EOIGW + route ::/0
EOIGW_ID="$(aws ec2 describe-egress-only-internet-gateways --query "EgressOnlyInternetGateways[?Attachments[?VpcId=='$VPC_ID']].EgressOnlyInternetGatewayId" --output text | head -n1 || true)"
[ -n "${EOIGW_ID:-}" ] || EOIGW_ID="$(aws ec2 create-egress-only-internet-gateway --vpc-id "$VPC_ID" --query "EgressOnlyInternetGateway.EgressOnlyInternetGatewayId" --output text)"
aws ec2 replace-route --route-table-id "$ROUTE_TABLE_ID" --destination-ipv6-cidr-block "::/0" --egress-only-internet-gateway-id "$EOIGW_ID" >/dev/null 2>&1 || \
aws ec2 create-route  --route-table-id "$ROUTE_TABLE_ID" --destination-ipv6-cidr-block "::/0" --egress-only-internet-gateway-id "$EOIGW_ID" >/dev/null

# Assign IPv6 to ENI + allow v6 egress in SG
aws ec2 assign-ipv6-addresses --network-interface-id "$ENI_ID" --ipv6-address-count 1 >/dev/null || true
SG_ID="$(aws ec2 describe-network-interfaces --network-interface-ids "$ENI_ID" --query "NetworkInterfaces[0].Groups[0].GroupId" --output text)"
aws ec2 authorize-security-group-egress --group-id "$SG_ID" --ip-permissions '[{"IpProtocol":"-1","Ipv6Ranges":[{"CidrIpv6":"::/0"}]}]' >/dev/null 2>&1 || true

# Reboot instance
INSTANCE_ID="$(aws ec2 describe-network-interfaces --network-interface-ids "$ENI_ID" --query "NetworkInterfaces[0].Attachment.InstanceId" --output text)"
aws ec2 reboot-instances --instance-ids "$INSTANCE_ID" >/dev/null
