"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ComputeStack = void 0;
const cdk = require("aws-cdk-lib");
const autoscaling = require("aws-cdk-lib/aws-autoscaling");
const ec2 = require("aws-cdk-lib/aws-ec2");
const elbv2 = require("aws-cdk-lib/aws-elasticloadbalancingv2");
const iam = require("aws-cdk-lib/aws-iam");
const lambda = require("aws-cdk-lib/aws-lambda");
const lambdaEventSources = require("aws-cdk-lib/aws-lambda-event-sources");
const aws_lambda_nodejs_1 = require("aws-cdk-lib/aws-lambda-nodejs");
const logs = require("aws-cdk-lib/aws-logs");
const path = require("path");
class ComputeStack extends cdk.Stack {
    loadBalancer;
    autoScalingGroup;
    constructor(scope, id, props) {
        super(scope, id, props);
        const instanceRole = new iam.Role(this, 'HostInstanceRole', {
            assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
            description: 'Kercel EC2 host role for artifact fetch and SSM management',
        });
        props.artifactsBucket.grantRead(instanceRole);
        instanceRole.addManagedPolicy(iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'));
        const userData = ec2.UserData.forLinux();
        userData.addCommands('set -euxo pipefail', 'dnf update -y', 'dnf install -y nginx git nodejs npm', 'systemctl enable nginx', 'mkdir -p /var/www/kercel', 'chown -R nginx:nginx /var/www/kercel', 'cat > /etc/nginx/conf.d/kercel.conf <<\'EOF\'', 'server {', '    listen 80 default_server;', '    server_name _;', '    root /var/www/kercel/current;', '    index index.html;', '    location / {', '        try_files $uri $uri/ /index.html;', '    }', '}', 'EOF', 'systemctl restart nginx');
        this.autoScalingGroup = new autoscaling.AutoScalingGroup(this, 'HostAsg', {
            vpc: props.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            securityGroup: props.instanceSecurityGroup,
            instanceType: new ec2.InstanceType(props.config.instanceType),
            machineImage: ec2.MachineImage.latestAmazonLinux2023(),
            role: instanceRole,
            userData,
            minCapacity: props.config.minCapacity,
            maxCapacity: props.config.maxCapacity,
            desiredCapacity: props.config.desiredCapacity,
            healthCheck: autoscaling.HealthCheck.elb({
                grace: cdk.Duration.minutes(5),
            }),
        });
        this.loadBalancer = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
            vpc: props.vpc,
            internetFacing: true,
            securityGroup: props.albSecurityGroup,
            vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
        });
        const listener = this.loadBalancer.addListener('HttpListener', {
            port: 80,
            open: false,
        });
        listener.addTargets('AsgTargets', {
            port: 80,
            targets: [this.autoScalingGroup],
            healthCheck: {
                path: '/',
                healthyHttpCodes: '200-399',
            },
        });
        const deployWorker = new aws_lambda_nodejs_1.NodejsFunction(this, 'DeployWorker', {
            functionName: `kercel-deploy-worker-${props.stage}`,
            entry: path.join(__dirname, '../../lambda/deploy-worker/index.ts'),
            handler: 'handler',
            runtime: lambda.Runtime.NODEJS_20_X,
            timeout: cdk.Duration.minutes(5),
            memorySize: 1024,
            vpc: props.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            environment: {
                STAGE: props.stage,
                PROJECTS_TABLE: props.projectsTable.tableName,
                DEPLOYMENTS_TABLE: props.deploymentsTable.tableName,
                ARTIFACTS_BUCKET: props.artifactsBucket.bucketName,
                DEPLOYMENT_QUEUE_URL: props.deploymentQueue.queueUrl,
            },
            logRetention: logs.RetentionDays.ONE_WEEK,
            bundling: {
                minify: true,
                sourceMap: true,
                externalModules: ['@aws-sdk/client-dynamodb', '@aws-sdk/lib-dynamodb', '@aws-sdk/client-s3'],
            },
        });
        props.projectsTable.grantReadWriteData(deployWorker);
        props.deploymentsTable.grantReadWriteData(deployWorker);
        props.artifactsBucket.grantReadWrite(deployWorker);
        props.deploymentQueue.grantConsumeMessages(deployWorker);
        deployWorker.addToRolePolicy(new iam.PolicyStatement({
            actions: ['ssm:SendCommand', 'ssm:GetCommandInvocation', 'ssm:ListCommands'],
            resources: ['*'],
        }));
        deployWorker.addToRolePolicy(new iam.PolicyStatement({
            actions: ['ec2:DescribeInstances'],
            resources: ['*'],
        }));
        deployWorker.addEventSource(new lambdaEventSources.SqsEventSource(props.deploymentQueue, {
            batchSize: 1,
            reportBatchItemFailures: true,
        }));
        new cdk.CfnOutput(this, 'LoadBalancerDns', {
            value: this.loadBalancer.loadBalancerDnsName,
        });
        new cdk.CfnOutput(this, 'DeployWorkerArn', {
            value: deployWorker.functionArn,
        });
    }
}
exports.ComputeStack = ComputeStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29tcHV0ZS1zdGFjay5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIi4uLy4uLy4uL2xpYi9zdGFja3MvY29tcHV0ZS1zdGFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSxtQ0FBbUM7QUFDbkMsMkRBQTJEO0FBRTNELDJDQUEyQztBQUMzQyxnRUFBZ0U7QUFDaEUsMkNBQTJDO0FBQzNDLGlEQUFpRDtBQUNqRCwyRUFBMkU7QUFDM0UscUVBQStEO0FBQy9ELDZDQUE2QztBQUk3Qyw2QkFBNkI7QUFlN0IsTUFBYSxZQUFhLFNBQVEsR0FBRyxDQUFDLEtBQUs7SUFDaEMsWUFBWSxDQUFnQztJQUM1QyxnQkFBZ0IsQ0FBK0I7SUFFeEQsWUFBWSxLQUFnQixFQUFFLEVBQVUsRUFBRSxLQUF3QjtRQUNoRSxLQUFLLENBQUMsS0FBSyxFQUFFLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUV4QixNQUFNLFlBQVksR0FBRyxJQUFJLEdBQUcsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLGtCQUFrQixFQUFFO1lBQzFELFNBQVMsRUFBRSxJQUFJLEdBQUcsQ0FBQyxnQkFBZ0IsQ0FBQyxtQkFBbUIsQ0FBQztZQUN4RCxXQUFXLEVBQUUsNERBQTREO1NBQzFFLENBQUMsQ0FBQztRQUNILEtBQUssQ0FBQyxlQUFlLENBQUMsU0FBUyxDQUFDLFlBQVksQ0FBQyxDQUFDO1FBQzlDLFlBQVksQ0FBQyxnQkFBZ0IsQ0FDM0IsR0FBRyxDQUFDLGFBQWEsQ0FBQyx3QkFBd0IsQ0FBQyw4QkFBOEIsQ0FBQyxDQUMzRSxDQUFDO1FBRUYsTUFBTSxRQUFRLEdBQUcsR0FBRyxDQUFDLFFBQVEsQ0FBQyxRQUFRLEVBQUUsQ0FBQztRQUN6QyxRQUFRLENBQUMsV0FBVyxDQUNsQixvQkFBb0IsRUFDcEIsZUFBZSxFQUNmLHFDQUFxQyxFQUNyQyx3QkFBd0IsRUFDeEIsMEJBQTBCLEVBQzFCLHNDQUFzQyxFQUN0QywrQ0FBK0MsRUFDL0MsVUFBVSxFQUNWLCtCQUErQixFQUMvQixvQkFBb0IsRUFDcEIsbUNBQW1DLEVBQ25DLHVCQUF1QixFQUN2QixrQkFBa0IsRUFDbEIsMkNBQTJDLEVBQzNDLE9BQU8sRUFDUCxHQUFHLEVBQ0gsS0FBSyxFQUNMLHlCQUF5QixDQUMxQixDQUFDO1FBRUYsSUFBSSxDQUFDLGdCQUFnQixHQUFHLElBQUksV0FBVyxDQUFDLGdCQUFnQixDQUFDLElBQUksRUFBRSxTQUFTLEVBQUU7WUFDeEUsR0FBRyxFQUFFLEtBQUssQ0FBQyxHQUFHO1lBQ2QsVUFBVSxFQUFFLEVBQUUsVUFBVSxFQUFFLEdBQUcsQ0FBQyxVQUFVLENBQUMsbUJBQW1CLEVBQUU7WUFDOUQsYUFBYSxFQUFFLEtBQUssQ0FBQyxxQkFBcUI7WUFDMUMsWUFBWSxFQUFFLElBQUksR0FBRyxDQUFDLFlBQVksQ0FBQyxLQUFLLENBQUMsTUFBTSxDQUFDLFlBQVksQ0FBQztZQUM3RCxZQUFZLEVBQUUsR0FBRyxDQUFDLFlBQVksQ0FBQyxxQkFBcUIsRUFBRTtZQUN0RCxJQUFJLEVBQUUsWUFBWTtZQUNsQixRQUFRO1lBQ1IsV0FBVyxFQUFFLEtBQUssQ0FBQyxNQUFNLENBQUMsV0FBVztZQUNyQyxXQUFXLEVBQUUsS0FBSyxDQUFDLE1BQU0sQ0FBQyxXQUFXO1lBQ3JDLGVBQWUsRUFBRSxLQUFLLENBQUMsTUFBTSxDQUFDLGVBQWU7WUFDN0MsV0FBVyxFQUFFLFdBQVcsQ0FBQyxXQUFXLENBQUMsR0FBRyxDQUFDO2dCQUN2QyxLQUFLLEVBQUUsR0FBRyxDQUFDLFFBQVEsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDO2FBQy9CLENBQUM7U0FDSCxDQUFDLENBQUM7UUFFSCxJQUFJLENBQUMsWUFBWSxHQUFHLElBQUksS0FBSyxDQUFDLHVCQUF1QixDQUFDLElBQUksRUFBRSxLQUFLLEVBQUU7WUFDakUsR0FBRyxFQUFFLEtBQUssQ0FBQyxHQUFHO1lBQ2QsY0FBYyxFQUFFLElBQUk7WUFDcEIsYUFBYSxFQUFFLEtBQUssQ0FBQyxnQkFBZ0I7WUFDckMsVUFBVSxFQUFFLEVBQUUsVUFBVSxFQUFFLEdBQUcsQ0FBQyxVQUFVLENBQUMsTUFBTSxFQUFFO1NBQ2xELENBQUMsQ0FBQztRQUVILE1BQU0sUUFBUSxHQUFHLElBQUksQ0FBQyxZQUFZLENBQUMsV0FBVyxDQUFDLGNBQWMsRUFBRTtZQUM3RCxJQUFJLEVBQUUsRUFBRTtZQUNSLElBQUksRUFBRSxLQUFLO1NBQ1osQ0FBQyxDQUFDO1FBRUgsUUFBUSxDQUFDLFVBQVUsQ0FBQyxZQUFZLEVBQUU7WUFDaEMsSUFBSSxFQUFFLEVBQUU7WUFDUixPQUFPLEVBQUUsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUM7WUFDaEMsV0FBVyxFQUFFO2dCQUNYLElBQUksRUFBRSxHQUFHO2dCQUNULGdCQUFnQixFQUFFLFNBQVM7YUFDNUI7U0FDRixDQUFDLENBQUM7UUFFSCxNQUFNLFlBQVksR0FBRyxJQUFJLGtDQUFjLENBQUMsSUFBSSxFQUFFLGNBQWMsRUFBRTtZQUM1RCxZQUFZLEVBQUUsd0JBQXdCLEtBQUssQ0FBQyxLQUFLLEVBQUU7WUFDbkQsS0FBSyxFQUFFLElBQUksQ0FBQyxJQUFJLENBQUMsU0FBUyxFQUFFLHFDQUFxQyxDQUFDO1lBQ2xFLE9BQU8sRUFBRSxTQUFTO1lBQ2xCLE9BQU8sRUFBRSxNQUFNLENBQUMsT0FBTyxDQUFDLFdBQVc7WUFDbkMsT0FBTyxFQUFFLEdBQUcsQ0FBQyxRQUFRLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQztZQUNoQyxVQUFVLEVBQUUsSUFBSTtZQUNoQixHQUFHLEVBQUUsS0FBSyxDQUFDLEdBQUc7WUFDZCxVQUFVLEVBQUUsRUFBRSxVQUFVLEVBQUUsR0FBRyxDQUFDLFVBQVUsQ0FBQyxtQkFBbUIsRUFBRTtZQUM5RCxXQUFXLEVBQUU7Z0JBQ1gsS0FBSyxFQUFFLEtBQUssQ0FBQyxLQUFLO2dCQUNsQixjQUFjLEVBQUUsS0FBSyxDQUFDLGFBQWEsQ0FBQyxTQUFTO2dCQUM3QyxpQkFBaUIsRUFBRSxLQUFLLENBQUMsZ0JBQWdCLENBQUMsU0FBUztnQkFDbkQsZ0JBQWdCLEVBQUUsS0FBSyxDQUFDLGVBQWUsQ0FBQyxVQUFVO2dCQUNsRCxvQkFBb0IsRUFBRSxLQUFLLENBQUMsZUFBZSxDQUFDLFFBQVE7YUFDckQ7WUFDRCxZQUFZLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxRQUFRO1lBQ3pDLFFBQVEsRUFBRTtnQkFDUixNQUFNLEVBQUUsSUFBSTtnQkFDWixTQUFTLEVBQUUsSUFBSTtnQkFDZixlQUFlLEVBQUUsQ0FBQywwQkFBMEIsRUFBRSx1QkFBdUIsRUFBRSxvQkFBb0IsQ0FBQzthQUM3RjtTQUNGLENBQUMsQ0FBQztRQUVILEtBQUssQ0FBQyxhQUFhLENBQUMsa0JBQWtCLENBQUMsWUFBWSxDQUFDLENBQUM7UUFDckQsS0FBSyxDQUFDLGdCQUFnQixDQUFDLGtCQUFrQixDQUFDLFlBQVksQ0FBQyxDQUFDO1FBQ3hELEtBQUssQ0FBQyxlQUFlLENBQUMsY0FBYyxDQUFDLFlBQVksQ0FBQyxDQUFDO1FBQ25ELEtBQUssQ0FBQyxlQUFlLENBQUMsb0JBQW9CLENBQUMsWUFBWSxDQUFDLENBQUM7UUFFekQsWUFBWSxDQUFDLGVBQWUsQ0FDMUIsSUFBSSxHQUFHLENBQUMsZUFBZSxDQUFDO1lBQ3RCLE9BQU8sRUFBRSxDQUFDLGlCQUFpQixFQUFFLDBCQUEwQixFQUFFLGtCQUFrQixDQUFDO1lBQzVFLFNBQVMsRUFBRSxDQUFDLEdBQUcsQ0FBQztTQUNqQixDQUFDLENBQ0gsQ0FBQztRQUNGLFlBQVksQ0FBQyxlQUFlLENBQzFCLElBQUksR0FBRyxDQUFDLGVBQWUsQ0FBQztZQUN0QixPQUFPLEVBQUUsQ0FBQyx1QkFBdUIsQ0FBQztZQUNsQyxTQUFTLEVBQUUsQ0FBQyxHQUFHLENBQUM7U0FDakIsQ0FBQyxDQUNILENBQUM7UUFFRixZQUFZLENBQUMsY0FBYyxDQUN6QixJQUFJLGtCQUFrQixDQUFDLGNBQWMsQ0FBQyxLQUFLLENBQUMsZUFBZSxFQUFFO1lBQzNELFNBQVMsRUFBRSxDQUFDO1lBQ1osdUJBQXVCLEVBQUUsSUFBSTtTQUM5QixDQUFDLENBQ0gsQ0FBQztRQUVGLElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsaUJBQWlCLEVBQUU7WUFDekMsS0FBSyxFQUFFLElBQUksQ0FBQyxZQUFZLENBQUMsbUJBQW1CO1NBQzdDLENBQUMsQ0FBQztRQUNILElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsaUJBQWlCLEVBQUU7WUFDekMsS0FBSyxFQUFFLFlBQVksQ0FBQyxXQUFXO1NBQ2hDLENBQUMsQ0FBQztJQUNMLENBQUM7Q0FDRjtBQW5JRCxvQ0FtSUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgKiBhcyBjZGsgZnJvbSAnYXdzLWNkay1saWInO1xyXG5pbXBvcnQgKiBhcyBhdXRvc2NhbGluZyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtYXV0b3NjYWxpbmcnO1xyXG5pbXBvcnQgKiBhcyBkeW5hbW9kYiBmcm9tICdhd3MtY2RrLWxpYi9hd3MtZHluYW1vZGInO1xyXG5pbXBvcnQgKiBhcyBlYzIgZnJvbSAnYXdzLWNkay1saWIvYXdzLWVjMic7XHJcbmltcG9ydCAqIGFzIGVsYnYyIGZyb20gJ2F3cy1jZGstbGliL2F3cy1lbGFzdGljbG9hZGJhbGFuY2luZ3YyJztcclxuaW1wb3J0ICogYXMgaWFtIGZyb20gJ2F3cy1jZGstbGliL2F3cy1pYW0nO1xyXG5pbXBvcnQgKiBhcyBsYW1iZGEgZnJvbSAnYXdzLWNkay1saWIvYXdzLWxhbWJkYSc7XHJcbmltcG9ydCAqIGFzIGxhbWJkYUV2ZW50U291cmNlcyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtbGFtYmRhLWV2ZW50LXNvdXJjZXMnO1xyXG5pbXBvcnQgeyBOb2RlanNGdW5jdGlvbiB9IGZyb20gJ2F3cy1jZGstbGliL2F3cy1sYW1iZGEtbm9kZWpzJztcclxuaW1wb3J0ICogYXMgbG9ncyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtbG9ncyc7XHJcbmltcG9ydCAqIGFzIHMzIGZyb20gJ2F3cy1jZGstbGliL2F3cy1zMyc7XHJcbmltcG9ydCAqIGFzIHNxcyBmcm9tICdhd3MtY2RrLWxpYi9hd3Mtc3FzJztcclxuaW1wb3J0IHsgQ29uc3RydWN0IH0gZnJvbSAnY29uc3RydWN0cyc7XHJcbmltcG9ydCAqIGFzIHBhdGggZnJvbSAncGF0aCc7XHJcbmltcG9ydCB7IEtlcmNlbFN0YWdlQ29uZmlnIH0gZnJvbSAnLi4vY29uZmlnJztcclxuXHJcbmV4cG9ydCBpbnRlcmZhY2UgQ29tcHV0ZVN0YWNrUHJvcHMgZXh0ZW5kcyBjZGsuU3RhY2tQcm9wcyB7XHJcbiAgcmVhZG9ubHkgc3RhZ2U6IHN0cmluZztcclxuICByZWFkb25seSBjb25maWc6IEtlcmNlbFN0YWdlQ29uZmlnO1xyXG4gIHJlYWRvbmx5IHZwYzogZWMyLklWcGM7XHJcbiAgcmVhZG9ubHkgYWxiU2VjdXJpdHlHcm91cDogZWMyLklTZWN1cml0eUdyb3VwO1xyXG4gIHJlYWRvbmx5IGluc3RhbmNlU2VjdXJpdHlHcm91cDogZWMyLklTZWN1cml0eUdyb3VwO1xyXG4gIHJlYWRvbmx5IHByb2plY3RzVGFibGU6IGR5bmFtb2RiLklUYWJsZTtcclxuICByZWFkb25seSBkZXBsb3ltZW50c1RhYmxlOiBkeW5hbW9kYi5JVGFibGU7XHJcbiAgcmVhZG9ubHkgYXJ0aWZhY3RzQnVja2V0OiBzMy5JQnVja2V0O1xyXG4gIHJlYWRvbmx5IGRlcGxveW1lbnRRdWV1ZTogc3FzLklRdWV1ZTtcclxufVxyXG5cclxuZXhwb3J0IGNsYXNzIENvbXB1dGVTdGFjayBleHRlbmRzIGNkay5TdGFjayB7XHJcbiAgcmVhZG9ubHkgbG9hZEJhbGFuY2VyOiBlbGJ2Mi5BcHBsaWNhdGlvbkxvYWRCYWxhbmNlcjtcclxuICByZWFkb25seSBhdXRvU2NhbGluZ0dyb3VwOiBhdXRvc2NhbGluZy5BdXRvU2NhbGluZ0dyb3VwO1xyXG5cclxuICBjb25zdHJ1Y3RvcihzY29wZTogQ29uc3RydWN0LCBpZDogc3RyaW5nLCBwcm9wczogQ29tcHV0ZVN0YWNrUHJvcHMpIHtcclxuICAgIHN1cGVyKHNjb3BlLCBpZCwgcHJvcHMpO1xyXG5cclxuICAgIGNvbnN0IGluc3RhbmNlUm9sZSA9IG5ldyBpYW0uUm9sZSh0aGlzLCAnSG9zdEluc3RhbmNlUm9sZScsIHtcclxuICAgICAgYXNzdW1lZEJ5OiBuZXcgaWFtLlNlcnZpY2VQcmluY2lwYWwoJ2VjMi5hbWF6b25hd3MuY29tJyksXHJcbiAgICAgIGRlc2NyaXB0aW9uOiAnS2VyY2VsIEVDMiBob3N0IHJvbGUgZm9yIGFydGlmYWN0IGZldGNoIGFuZCBTU00gbWFuYWdlbWVudCcsXHJcbiAgICB9KTtcclxuICAgIHByb3BzLmFydGlmYWN0c0J1Y2tldC5ncmFudFJlYWQoaW5zdGFuY2VSb2xlKTtcclxuICAgIGluc3RhbmNlUm9sZS5hZGRNYW5hZ2VkUG9saWN5KFxyXG4gICAgICBpYW0uTWFuYWdlZFBvbGljeS5mcm9tQXdzTWFuYWdlZFBvbGljeU5hbWUoJ0FtYXpvblNTTU1hbmFnZWRJbnN0YW5jZUNvcmUnKSxcclxuICAgICk7XHJcblxyXG4gICAgY29uc3QgdXNlckRhdGEgPSBlYzIuVXNlckRhdGEuZm9yTGludXgoKTtcclxuICAgIHVzZXJEYXRhLmFkZENvbW1hbmRzKFxyXG4gICAgICAnc2V0IC1ldXhvIHBpcGVmYWlsJyxcclxuICAgICAgJ2RuZiB1cGRhdGUgLXknLFxyXG4gICAgICAnZG5mIGluc3RhbGwgLXkgbmdpbnggZ2l0IG5vZGVqcyBucG0nLFxyXG4gICAgICAnc3lzdGVtY3RsIGVuYWJsZSBuZ2lueCcsXHJcbiAgICAgICdta2RpciAtcCAvdmFyL3d3dy9rZXJjZWwnLFxyXG4gICAgICAnY2hvd24gLVIgbmdpbng6bmdpbnggL3Zhci93d3cva2VyY2VsJyxcclxuICAgICAgJ2NhdCA+IC9ldGMvbmdpbngvY29uZi5kL2tlcmNlbC5jb25mIDw8XFwnRU9GXFwnJyxcclxuICAgICAgJ3NlcnZlciB7JyxcclxuICAgICAgJyAgICBsaXN0ZW4gODAgZGVmYXVsdF9zZXJ2ZXI7JyxcclxuICAgICAgJyAgICBzZXJ2ZXJfbmFtZSBfOycsXHJcbiAgICAgICcgICAgcm9vdCAvdmFyL3d3dy9rZXJjZWwvY3VycmVudDsnLFxyXG4gICAgICAnICAgIGluZGV4IGluZGV4Lmh0bWw7JyxcclxuICAgICAgJyAgICBsb2NhdGlvbiAvIHsnLFxyXG4gICAgICAnICAgICAgICB0cnlfZmlsZXMgJHVyaSAkdXJpLyAvaW5kZXguaHRtbDsnLFxyXG4gICAgICAnICAgIH0nLFxyXG4gICAgICAnfScsXHJcbiAgICAgICdFT0YnLFxyXG4gICAgICAnc3lzdGVtY3RsIHJlc3RhcnQgbmdpbngnLFxyXG4gICAgKTtcclxuXHJcbiAgICB0aGlzLmF1dG9TY2FsaW5nR3JvdXAgPSBuZXcgYXV0b3NjYWxpbmcuQXV0b1NjYWxpbmdHcm91cCh0aGlzLCAnSG9zdEFzZycsIHtcclxuICAgICAgdnBjOiBwcm9wcy52cGMsXHJcbiAgICAgIHZwY1N1Ym5ldHM6IHsgc3VibmV0VHlwZTogZWMyLlN1Ym5ldFR5cGUuUFJJVkFURV9XSVRIX0VHUkVTUyB9LFxyXG4gICAgICBzZWN1cml0eUdyb3VwOiBwcm9wcy5pbnN0YW5jZVNlY3VyaXR5R3JvdXAsXHJcbiAgICAgIGluc3RhbmNlVHlwZTogbmV3IGVjMi5JbnN0YW5jZVR5cGUocHJvcHMuY29uZmlnLmluc3RhbmNlVHlwZSksXHJcbiAgICAgIG1hY2hpbmVJbWFnZTogZWMyLk1hY2hpbmVJbWFnZS5sYXRlc3RBbWF6b25MaW51eDIwMjMoKSxcclxuICAgICAgcm9sZTogaW5zdGFuY2VSb2xlLFxyXG4gICAgICB1c2VyRGF0YSxcclxuICAgICAgbWluQ2FwYWNpdHk6IHByb3BzLmNvbmZpZy5taW5DYXBhY2l0eSxcclxuICAgICAgbWF4Q2FwYWNpdHk6IHByb3BzLmNvbmZpZy5tYXhDYXBhY2l0eSxcclxuICAgICAgZGVzaXJlZENhcGFjaXR5OiBwcm9wcy5jb25maWcuZGVzaXJlZENhcGFjaXR5LFxyXG4gICAgICBoZWFsdGhDaGVjazogYXV0b3NjYWxpbmcuSGVhbHRoQ2hlY2suZWxiKHtcclxuICAgICAgICBncmFjZTogY2RrLkR1cmF0aW9uLm1pbnV0ZXMoNSksXHJcbiAgICAgIH0pLFxyXG4gICAgfSk7XHJcblxyXG4gICAgdGhpcy5sb2FkQmFsYW5jZXIgPSBuZXcgZWxidjIuQXBwbGljYXRpb25Mb2FkQmFsYW5jZXIodGhpcywgJ0FsYicsIHtcclxuICAgICAgdnBjOiBwcm9wcy52cGMsXHJcbiAgICAgIGludGVybmV0RmFjaW5nOiB0cnVlLFxyXG4gICAgICBzZWN1cml0eUdyb3VwOiBwcm9wcy5hbGJTZWN1cml0eUdyb3VwLFxyXG4gICAgICB2cGNTdWJuZXRzOiB7IHN1Ym5ldFR5cGU6IGVjMi5TdWJuZXRUeXBlLlBVQkxJQyB9LFxyXG4gICAgfSk7XHJcblxyXG4gICAgY29uc3QgbGlzdGVuZXIgPSB0aGlzLmxvYWRCYWxhbmNlci5hZGRMaXN0ZW5lcignSHR0cExpc3RlbmVyJywge1xyXG4gICAgICBwb3J0OiA4MCxcclxuICAgICAgb3BlbjogZmFsc2UsXHJcbiAgICB9KTtcclxuXHJcbiAgICBsaXN0ZW5lci5hZGRUYXJnZXRzKCdBc2dUYXJnZXRzJywge1xyXG4gICAgICBwb3J0OiA4MCxcclxuICAgICAgdGFyZ2V0czogW3RoaXMuYXV0b1NjYWxpbmdHcm91cF0sXHJcbiAgICAgIGhlYWx0aENoZWNrOiB7XHJcbiAgICAgICAgcGF0aDogJy8nLFxyXG4gICAgICAgIGhlYWx0aHlIdHRwQ29kZXM6ICcyMDAtMzk5JyxcclxuICAgICAgfSxcclxuICAgIH0pO1xyXG5cclxuICAgIGNvbnN0IGRlcGxveVdvcmtlciA9IG5ldyBOb2RlanNGdW5jdGlvbih0aGlzLCAnRGVwbG95V29ya2VyJywge1xyXG4gICAgICBmdW5jdGlvbk5hbWU6IGBrZXJjZWwtZGVwbG95LXdvcmtlci0ke3Byb3BzLnN0YWdlfWAsXHJcbiAgICAgIGVudHJ5OiBwYXRoLmpvaW4oX19kaXJuYW1lLCAnLi4vLi4vbGFtYmRhL2RlcGxveS13b3JrZXIvaW5kZXgudHMnKSxcclxuICAgICAgaGFuZGxlcjogJ2hhbmRsZXInLFxyXG4gICAgICBydW50aW1lOiBsYW1iZGEuUnVudGltZS5OT0RFSlNfMjBfWCxcclxuICAgICAgdGltZW91dDogY2RrLkR1cmF0aW9uLm1pbnV0ZXMoNSksXHJcbiAgICAgIG1lbW9yeVNpemU6IDEwMjQsXHJcbiAgICAgIHZwYzogcHJvcHMudnBjLFxyXG4gICAgICB2cGNTdWJuZXRzOiB7IHN1Ym5ldFR5cGU6IGVjMi5TdWJuZXRUeXBlLlBSSVZBVEVfV0lUSF9FR1JFU1MgfSxcclxuICAgICAgZW52aXJvbm1lbnQ6IHtcclxuICAgICAgICBTVEFHRTogcHJvcHMuc3RhZ2UsXHJcbiAgICAgICAgUFJPSkVDVFNfVEFCTEU6IHByb3BzLnByb2plY3RzVGFibGUudGFibGVOYW1lLFxyXG4gICAgICAgIERFUExPWU1FTlRTX1RBQkxFOiBwcm9wcy5kZXBsb3ltZW50c1RhYmxlLnRhYmxlTmFtZSxcclxuICAgICAgICBBUlRJRkFDVFNfQlVDS0VUOiBwcm9wcy5hcnRpZmFjdHNCdWNrZXQuYnVja2V0TmFtZSxcclxuICAgICAgICBERVBMT1lNRU5UX1FVRVVFX1VSTDogcHJvcHMuZGVwbG95bWVudFF1ZXVlLnF1ZXVlVXJsLFxyXG4gICAgICB9LFxyXG4gICAgICBsb2dSZXRlbnRpb246IGxvZ3MuUmV0ZW50aW9uRGF5cy5PTkVfV0VFSyxcclxuICAgICAgYnVuZGxpbmc6IHtcclxuICAgICAgICBtaW5pZnk6IHRydWUsXHJcbiAgICAgICAgc291cmNlTWFwOiB0cnVlLFxyXG4gICAgICAgIGV4dGVybmFsTW9kdWxlczogWydAYXdzLXNkay9jbGllbnQtZHluYW1vZGInLCAnQGF3cy1zZGsvbGliLWR5bmFtb2RiJywgJ0Bhd3Mtc2RrL2NsaWVudC1zMyddLFxyXG4gICAgICB9LFxyXG4gICAgfSk7XHJcblxyXG4gICAgcHJvcHMucHJvamVjdHNUYWJsZS5ncmFudFJlYWRXcml0ZURhdGEoZGVwbG95V29ya2VyKTtcclxuICAgIHByb3BzLmRlcGxveW1lbnRzVGFibGUuZ3JhbnRSZWFkV3JpdGVEYXRhKGRlcGxveVdvcmtlcik7XHJcbiAgICBwcm9wcy5hcnRpZmFjdHNCdWNrZXQuZ3JhbnRSZWFkV3JpdGUoZGVwbG95V29ya2VyKTtcclxuICAgIHByb3BzLmRlcGxveW1lbnRRdWV1ZS5ncmFudENvbnN1bWVNZXNzYWdlcyhkZXBsb3lXb3JrZXIpO1xyXG5cclxuICAgIGRlcGxveVdvcmtlci5hZGRUb1JvbGVQb2xpY3koXHJcbiAgICAgIG5ldyBpYW0uUG9saWN5U3RhdGVtZW50KHtcclxuICAgICAgICBhY3Rpb25zOiBbJ3NzbTpTZW5kQ29tbWFuZCcsICdzc206R2V0Q29tbWFuZEludm9jYXRpb24nLCAnc3NtOkxpc3RDb21tYW5kcyddLFxyXG4gICAgICAgIHJlc291cmNlczogWycqJ10sXHJcbiAgICAgIH0pLFxyXG4gICAgKTtcclxuICAgIGRlcGxveVdvcmtlci5hZGRUb1JvbGVQb2xpY3koXHJcbiAgICAgIG5ldyBpYW0uUG9saWN5U3RhdGVtZW50KHtcclxuICAgICAgICBhY3Rpb25zOiBbJ2VjMjpEZXNjcmliZUluc3RhbmNlcyddLFxyXG4gICAgICAgIHJlc291cmNlczogWycqJ10sXHJcbiAgICAgIH0pLFxyXG4gICAgKTtcclxuXHJcbiAgICBkZXBsb3lXb3JrZXIuYWRkRXZlbnRTb3VyY2UoXHJcbiAgICAgIG5ldyBsYW1iZGFFdmVudFNvdXJjZXMuU3FzRXZlbnRTb3VyY2UocHJvcHMuZGVwbG95bWVudFF1ZXVlLCB7XHJcbiAgICAgICAgYmF0Y2hTaXplOiAxLFxyXG4gICAgICAgIHJlcG9ydEJhdGNoSXRlbUZhaWx1cmVzOiB0cnVlLFxyXG4gICAgICB9KSxcclxuICAgICk7XHJcblxyXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0xvYWRCYWxhbmNlckRucycsIHtcclxuICAgICAgdmFsdWU6IHRoaXMubG9hZEJhbGFuY2VyLmxvYWRCYWxhbmNlckRuc05hbWUsXHJcbiAgICB9KTtcclxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdEZXBsb3lXb3JrZXJBcm4nLCB7XHJcbiAgICAgIHZhbHVlOiBkZXBsb3lXb3JrZXIuZnVuY3Rpb25Bcm4sXHJcbiAgICB9KTtcclxuICB9XHJcbn1cclxuIl19