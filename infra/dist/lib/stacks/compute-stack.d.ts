import * as cdk from 'aws-cdk-lib';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
import { KercelStageConfig } from '../config';
export interface ComputeStackProps extends cdk.StackProps {
    readonly stage: string;
    readonly config: KercelStageConfig;
    readonly vpc: ec2.IVpc;
    readonly albSecurityGroup: ec2.ISecurityGroup;
    readonly instanceSecurityGroup: ec2.ISecurityGroup;
    readonly projectsTable: dynamodb.ITable;
    readonly deploymentsTable: dynamodb.ITable;
    readonly artifactsBucket: s3.IBucket;
    readonly deploymentQueue: sqs.IQueue;
}
export declare class ComputeStack extends cdk.Stack {
    readonly loadBalancer: elbv2.ApplicationLoadBalancer;
    readonly autoScalingGroup: autoscaling.AutoScalingGroup;
    constructor(scope: Construct, id: string, props: ComputeStackProps);
}
