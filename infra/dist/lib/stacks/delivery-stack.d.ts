import * as cdk from 'aws-cdk-lib';
import * as globalaccelerator from 'aws-cdk-lib/aws-globalaccelerator';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Construct } from 'constructs';
export interface DeliveryStackProps extends cdk.StackProps {
    readonly stage: string;
    readonly loadBalancer: elbv2.IApplicationLoadBalancer;
}
export declare class DeliveryStack extends cdk.Stack {
    readonly accelerator: globalaccelerator.Accelerator;
    constructor(scope: Construct, id: string, props: DeliveryStackProps);
}
