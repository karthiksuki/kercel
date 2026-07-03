"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiStack = void 0;
const cdk = require("aws-cdk-lib");
const apigateway = require("aws-cdk-lib/aws-apigateway");
const lambda = require("aws-cdk-lib/aws-lambda");
const aws_lambda_nodejs_1 = require("aws-cdk-lib/aws-lambda-nodejs");
const logs = require("aws-cdk-lib/aws-logs");
const path = require("path");
class ApiStack extends cdk.Stack {
    api;
    constructor(scope, id, props) {
        super(scope, id, props);
        const apiHandler = new aws_lambda_nodejs_1.NodejsFunction(this, 'ApiHandler', {
            functionName: `kercel-api-${props.stage}`,
            entry: path.join(__dirname, '../../lambda/api/index.ts'),
            handler: 'handler',
            runtime: lambda.Runtime.NODEJS_20_X,
            timeout: cdk.Duration.seconds(29),
            memorySize: 512,
            environment: {
                STAGE: props.stage,
                PROJECTS_TABLE: props.projectsTable.tableName,
                DEPLOYMENTS_TABLE: props.deploymentsTable.tableName,
                DEPLOYMENT_QUEUE_URL: props.deploymentQueue.queueUrl,
            },
            logRetention: logs.RetentionDays.ONE_WEEK,
            bundling: {
                minify: true,
                sourceMap: true,
                externalModules: [
                    '@aws-sdk/client-dynamodb',
                    '@aws-sdk/lib-dynamodb',
                    '@aws-sdk/client-sqs',
                ],
            },
        });
        props.projectsTable.grantReadWriteData(apiHandler);
        props.deploymentsTable.grantReadWriteData(apiHandler);
        props.deploymentQueue.grantSendMessages(apiHandler);
        this.api = new apigateway.RestApi(this, 'KercelApi', {
            restApiName: `kercel-api-${props.stage}`,
            description: 'Kercel control plane API',
            deployOptions: {
                stageName: props.stage,
                throttlingRateLimit: 100,
                throttlingBurstLimit: 200,
            },
            defaultCorsPreflightOptions: {
                allowOrigins: apigateway.Cors.ALL_ORIGINS,
                allowMethods: apigateway.Cors.ALL_METHODS,
                allowHeaders: ['Content-Type', 'Authorization'],
            },
        });
        const integration = new apigateway.LambdaIntegration(apiHandler);
        const projects = this.api.root.addResource('projects');
        projects.addMethod('POST', integration);
        projects.addMethod('GET', integration);
        const project = projects.addResource('{projectId}');
        project.addMethod('GET', integration);
        const deployments = project.addResource('deployments');
        deployments.addMethod('POST', integration);
        deployments.addMethod('GET', integration);
        const deployment = deployments.addResource('{deploymentId}');
        deployment.addMethod('GET', integration);
        new cdk.CfnOutput(this, 'ApiUrl', {
            value: this.api.url,
            description: 'Kercel API base URL',
        });
    }
}
exports.ApiStack = ApiStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLXN0YWNrLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiLi4vLi4vLi4vbGliL3N0YWNrcy9hcGktc3RhY2sudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsbUNBQW1DO0FBQ25DLHlEQUF5RDtBQUV6RCxpREFBaUQ7QUFDakQscUVBQStEO0FBQy9ELDZDQUE2QztBQUc3Qyw2QkFBNkI7QUFTN0IsTUFBYSxRQUFTLFNBQVEsR0FBRyxDQUFDLEtBQUs7SUFDNUIsR0FBRyxDQUFxQjtJQUVqQyxZQUFZLEtBQWdCLEVBQUUsRUFBVSxFQUFFLEtBQW9CO1FBQzVELEtBQUssQ0FBQyxLQUFLLEVBQUUsRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBRXhCLE1BQU0sVUFBVSxHQUFHLElBQUksa0NBQWMsQ0FBQyxJQUFJLEVBQUUsWUFBWSxFQUFFO1lBQ3hELFlBQVksRUFBRSxjQUFjLEtBQUssQ0FBQyxLQUFLLEVBQUU7WUFDekMsS0FBSyxFQUFFLElBQUksQ0FBQyxJQUFJLENBQUMsU0FBUyxFQUFFLDJCQUEyQixDQUFDO1lBQ3hELE9BQU8sRUFBRSxTQUFTO1lBQ2xCLE9BQU8sRUFBRSxNQUFNLENBQUMsT0FBTyxDQUFDLFdBQVc7WUFDbkMsT0FBTyxFQUFFLEdBQUcsQ0FBQyxRQUFRLENBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztZQUNqQyxVQUFVLEVBQUUsR0FBRztZQUNmLFdBQVcsRUFBRTtnQkFDWCxLQUFLLEVBQUUsS0FBSyxDQUFDLEtBQUs7Z0JBQ2xCLGNBQWMsRUFBRSxLQUFLLENBQUMsYUFBYSxDQUFDLFNBQVM7Z0JBQzdDLGlCQUFpQixFQUFFLEtBQUssQ0FBQyxnQkFBZ0IsQ0FBQyxTQUFTO2dCQUNuRCxvQkFBb0IsRUFBRSxLQUFLLENBQUMsZUFBZSxDQUFDLFFBQVE7YUFDckQ7WUFDRCxZQUFZLEVBQUUsSUFBSSxDQUFDLGFBQWEsQ0FBQyxRQUFRO1lBQ3pDLFFBQVEsRUFBRTtnQkFDUixNQUFNLEVBQUUsSUFBSTtnQkFDWixTQUFTLEVBQUUsSUFBSTtnQkFDZixlQUFlLEVBQUU7b0JBQ2YsMEJBQTBCO29CQUMxQix1QkFBdUI7b0JBQ3ZCLHFCQUFxQjtpQkFDdEI7YUFDRjtTQUNGLENBQUMsQ0FBQztRQUVILEtBQUssQ0FBQyxhQUFhLENBQUMsa0JBQWtCLENBQUMsVUFBVSxDQUFDLENBQUM7UUFDbkQsS0FBSyxDQUFDLGdCQUFnQixDQUFDLGtCQUFrQixDQUFDLFVBQVUsQ0FBQyxDQUFDO1FBQ3RELEtBQUssQ0FBQyxlQUFlLENBQUMsaUJBQWlCLENBQUMsVUFBVSxDQUFDLENBQUM7UUFFcEQsSUFBSSxDQUFDLEdBQUcsR0FBRyxJQUFJLFVBQVUsQ0FBQyxPQUFPLENBQUMsSUFBSSxFQUFFLFdBQVcsRUFBRTtZQUNuRCxXQUFXLEVBQUUsY0FBYyxLQUFLLENBQUMsS0FBSyxFQUFFO1lBQ3hDLFdBQVcsRUFBRSwwQkFBMEI7WUFDdkMsYUFBYSxFQUFFO2dCQUNiLFNBQVMsRUFBRSxLQUFLLENBQUMsS0FBSztnQkFDdEIsbUJBQW1CLEVBQUUsR0FBRztnQkFDeEIsb0JBQW9CLEVBQUUsR0FBRzthQUMxQjtZQUNELDJCQUEyQixFQUFFO2dCQUMzQixZQUFZLEVBQUUsVUFBVSxDQUFDLElBQUksQ0FBQyxXQUFXO2dCQUN6QyxZQUFZLEVBQUUsVUFBVSxDQUFDLElBQUksQ0FBQyxXQUFXO2dCQUN6QyxZQUFZLEVBQUUsQ0FBQyxjQUFjLEVBQUUsZUFBZSxDQUFDO2FBQ2hEO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsTUFBTSxXQUFXLEdBQUcsSUFBSSxVQUFVLENBQUMsaUJBQWlCLENBQUMsVUFBVSxDQUFDLENBQUM7UUFFakUsTUFBTSxRQUFRLEdBQUcsSUFBSSxDQUFDLEdBQUcsQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLFVBQVUsQ0FBQyxDQUFDO1FBQ3ZELFFBQVEsQ0FBQyxTQUFTLENBQUMsTUFBTSxFQUFFLFdBQVcsQ0FBQyxDQUFDO1FBQ3hDLFFBQVEsQ0FBQyxTQUFTLENBQUMsS0FBSyxFQUFFLFdBQVcsQ0FBQyxDQUFDO1FBRXZDLE1BQU0sT0FBTyxHQUFHLFFBQVEsQ0FBQyxXQUFXLENBQUMsYUFBYSxDQUFDLENBQUM7UUFDcEQsT0FBTyxDQUFDLFNBQVMsQ0FBQyxLQUFLLEVBQUUsV0FBVyxDQUFDLENBQUM7UUFFdEMsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLFdBQVcsQ0FBQyxhQUFhLENBQUMsQ0FBQztRQUN2RCxXQUFXLENBQUMsU0FBUyxDQUFDLE1BQU0sRUFBRSxXQUFXLENBQUMsQ0FBQztRQUMzQyxXQUFXLENBQUMsU0FBUyxDQUFDLEtBQUssRUFBRSxXQUFXLENBQUMsQ0FBQztRQUUxQyxNQUFNLFVBQVUsR0FBRyxXQUFXLENBQUMsV0FBVyxDQUFDLGdCQUFnQixDQUFDLENBQUM7UUFDN0QsVUFBVSxDQUFDLFNBQVMsQ0FBQyxLQUFLLEVBQUUsV0FBVyxDQUFDLENBQUM7UUFFekMsSUFBSSxHQUFHLENBQUMsU0FBUyxDQUFDLElBQUksRUFBRSxRQUFRLEVBQUU7WUFDaEMsS0FBSyxFQUFFLElBQUksQ0FBQyxHQUFHLENBQUMsR0FBRztZQUNuQixXQUFXLEVBQUUscUJBQXFCO1NBQ25DLENBQUMsQ0FBQztJQUNMLENBQUM7Q0FDRjtBQXZFRCw0QkF1RUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgKiBhcyBjZGsgZnJvbSAnYXdzLWNkay1saWInO1xyXG5pbXBvcnQgKiBhcyBhcGlnYXRld2F5IGZyb20gJ2F3cy1jZGstbGliL2F3cy1hcGlnYXRld2F5JztcclxuaW1wb3J0ICogYXMgZHluYW1vZGIgZnJvbSAnYXdzLWNkay1saWIvYXdzLWR5bmFtb2RiJztcclxuaW1wb3J0ICogYXMgbGFtYmRhIGZyb20gJ2F3cy1jZGstbGliL2F3cy1sYW1iZGEnO1xyXG5pbXBvcnQgeyBOb2RlanNGdW5jdGlvbiB9IGZyb20gJ2F3cy1jZGstbGliL2F3cy1sYW1iZGEtbm9kZWpzJztcclxuaW1wb3J0ICogYXMgbG9ncyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtbG9ncyc7XHJcbmltcG9ydCAqIGFzIHNxcyBmcm9tICdhd3MtY2RrLWxpYi9hd3Mtc3FzJztcclxuaW1wb3J0IHsgQ29uc3RydWN0IH0gZnJvbSAnY29uc3RydWN0cyc7XHJcbmltcG9ydCAqIGFzIHBhdGggZnJvbSAncGF0aCc7XHJcblxyXG5leHBvcnQgaW50ZXJmYWNlIEFwaVN0YWNrUHJvcHMgZXh0ZW5kcyBjZGsuU3RhY2tQcm9wcyB7XHJcbiAgcmVhZG9ubHkgc3RhZ2U6IHN0cmluZztcclxuICByZWFkb25seSBwcm9qZWN0c1RhYmxlOiBkeW5hbW9kYi5JVGFibGU7XHJcbiAgcmVhZG9ubHkgZGVwbG95bWVudHNUYWJsZTogZHluYW1vZGIuSVRhYmxlO1xyXG4gIHJlYWRvbmx5IGRlcGxveW1lbnRRdWV1ZTogc3FzLklRdWV1ZTtcclxufVxyXG5cclxuZXhwb3J0IGNsYXNzIEFwaVN0YWNrIGV4dGVuZHMgY2RrLlN0YWNrIHtcclxuICByZWFkb25seSBhcGk6IGFwaWdhdGV3YXkuUmVzdEFwaTtcclxuXHJcbiAgY29uc3RydWN0b3Ioc2NvcGU6IENvbnN0cnVjdCwgaWQ6IHN0cmluZywgcHJvcHM6IEFwaVN0YWNrUHJvcHMpIHtcclxuICAgIHN1cGVyKHNjb3BlLCBpZCwgcHJvcHMpO1xyXG5cclxuICAgIGNvbnN0IGFwaUhhbmRsZXIgPSBuZXcgTm9kZWpzRnVuY3Rpb24odGhpcywgJ0FwaUhhbmRsZXInLCB7XHJcbiAgICAgIGZ1bmN0aW9uTmFtZTogYGtlcmNlbC1hcGktJHtwcm9wcy5zdGFnZX1gLFxyXG4gICAgICBlbnRyeTogcGF0aC5qb2luKF9fZGlybmFtZSwgJy4uLy4uL2xhbWJkYS9hcGkvaW5kZXgudHMnKSxcclxuICAgICAgaGFuZGxlcjogJ2hhbmRsZXInLFxyXG4gICAgICBydW50aW1lOiBsYW1iZGEuUnVudGltZS5OT0RFSlNfMjBfWCxcclxuICAgICAgdGltZW91dDogY2RrLkR1cmF0aW9uLnNlY29uZHMoMjkpLFxyXG4gICAgICBtZW1vcnlTaXplOiA1MTIsXHJcbiAgICAgIGVudmlyb25tZW50OiB7XHJcbiAgICAgICAgU1RBR0U6IHByb3BzLnN0YWdlLFxyXG4gICAgICAgIFBST0pFQ1RTX1RBQkxFOiBwcm9wcy5wcm9qZWN0c1RhYmxlLnRhYmxlTmFtZSxcclxuICAgICAgICBERVBMT1lNRU5UU19UQUJMRTogcHJvcHMuZGVwbG95bWVudHNUYWJsZS50YWJsZU5hbWUsXHJcbiAgICAgICAgREVQTE9ZTUVOVF9RVUVVRV9VUkw6IHByb3BzLmRlcGxveW1lbnRRdWV1ZS5xdWV1ZVVybCxcclxuICAgICAgfSxcclxuICAgICAgbG9nUmV0ZW50aW9uOiBsb2dzLlJldGVudGlvbkRheXMuT05FX1dFRUssXHJcbiAgICAgIGJ1bmRsaW5nOiB7XHJcbiAgICAgICAgbWluaWZ5OiB0cnVlLFxyXG4gICAgICAgIHNvdXJjZU1hcDogdHJ1ZSxcclxuICAgICAgICBleHRlcm5hbE1vZHVsZXM6IFtcclxuICAgICAgICAgICdAYXdzLXNkay9jbGllbnQtZHluYW1vZGInLFxyXG4gICAgICAgICAgJ0Bhd3Mtc2RrL2xpYi1keW5hbW9kYicsXHJcbiAgICAgICAgICAnQGF3cy1zZGsvY2xpZW50LXNxcycsXHJcbiAgICAgICAgXSxcclxuICAgICAgfSxcclxuICAgIH0pO1xyXG5cclxuICAgIHByb3BzLnByb2plY3RzVGFibGUuZ3JhbnRSZWFkV3JpdGVEYXRhKGFwaUhhbmRsZXIpO1xyXG4gICAgcHJvcHMuZGVwbG95bWVudHNUYWJsZS5ncmFudFJlYWRXcml0ZURhdGEoYXBpSGFuZGxlcik7XHJcbiAgICBwcm9wcy5kZXBsb3ltZW50UXVldWUuZ3JhbnRTZW5kTWVzc2FnZXMoYXBpSGFuZGxlcik7XHJcblxyXG4gICAgdGhpcy5hcGkgPSBuZXcgYXBpZ2F0ZXdheS5SZXN0QXBpKHRoaXMsICdLZXJjZWxBcGknLCB7XHJcbiAgICAgIHJlc3RBcGlOYW1lOiBga2VyY2VsLWFwaS0ke3Byb3BzLnN0YWdlfWAsXHJcbiAgICAgIGRlc2NyaXB0aW9uOiAnS2VyY2VsIGNvbnRyb2wgcGxhbmUgQVBJJyxcclxuICAgICAgZGVwbG95T3B0aW9uczoge1xyXG4gICAgICAgIHN0YWdlTmFtZTogcHJvcHMuc3RhZ2UsXHJcbiAgICAgICAgdGhyb3R0bGluZ1JhdGVMaW1pdDogMTAwLFxyXG4gICAgICAgIHRocm90dGxpbmdCdXJzdExpbWl0OiAyMDAsXHJcbiAgICAgIH0sXHJcbiAgICAgIGRlZmF1bHRDb3JzUHJlZmxpZ2h0T3B0aW9uczoge1xyXG4gICAgICAgIGFsbG93T3JpZ2luczogYXBpZ2F0ZXdheS5Db3JzLkFMTF9PUklHSU5TLFxyXG4gICAgICAgIGFsbG93TWV0aG9kczogYXBpZ2F0ZXdheS5Db3JzLkFMTF9NRVRIT0RTLFxyXG4gICAgICAgIGFsbG93SGVhZGVyczogWydDb250ZW50LVR5cGUnLCAnQXV0aG9yaXphdGlvbiddLFxyXG4gICAgICB9LFxyXG4gICAgfSk7XHJcblxyXG4gICAgY29uc3QgaW50ZWdyYXRpb24gPSBuZXcgYXBpZ2F0ZXdheS5MYW1iZGFJbnRlZ3JhdGlvbihhcGlIYW5kbGVyKTtcclxuXHJcbiAgICBjb25zdCBwcm9qZWN0cyA9IHRoaXMuYXBpLnJvb3QuYWRkUmVzb3VyY2UoJ3Byb2plY3RzJyk7XHJcbiAgICBwcm9qZWN0cy5hZGRNZXRob2QoJ1BPU1QnLCBpbnRlZ3JhdGlvbik7XHJcbiAgICBwcm9qZWN0cy5hZGRNZXRob2QoJ0dFVCcsIGludGVncmF0aW9uKTtcclxuXHJcbiAgICBjb25zdCBwcm9qZWN0ID0gcHJvamVjdHMuYWRkUmVzb3VyY2UoJ3twcm9qZWN0SWR9Jyk7XHJcbiAgICBwcm9qZWN0LmFkZE1ldGhvZCgnR0VUJywgaW50ZWdyYXRpb24pO1xyXG5cclxuICAgIGNvbnN0IGRlcGxveW1lbnRzID0gcHJvamVjdC5hZGRSZXNvdXJjZSgnZGVwbG95bWVudHMnKTtcclxuICAgIGRlcGxveW1lbnRzLmFkZE1ldGhvZCgnUE9TVCcsIGludGVncmF0aW9uKTtcclxuICAgIGRlcGxveW1lbnRzLmFkZE1ldGhvZCgnR0VUJywgaW50ZWdyYXRpb24pO1xyXG5cclxuICAgIGNvbnN0IGRlcGxveW1lbnQgPSBkZXBsb3ltZW50cy5hZGRSZXNvdXJjZSgne2RlcGxveW1lbnRJZH0nKTtcclxuICAgIGRlcGxveW1lbnQuYWRkTWV0aG9kKCdHRVQnLCBpbnRlZ3JhdGlvbik7XHJcblxyXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0FwaVVybCcsIHtcclxuICAgICAgdmFsdWU6IHRoaXMuYXBpLnVybCxcclxuICAgICAgZGVzY3JpcHRpb246ICdLZXJjZWwgQVBJIGJhc2UgVVJMJyxcclxuICAgIH0pO1xyXG4gIH1cclxufVxyXG4iXX0=