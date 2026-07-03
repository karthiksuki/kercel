import type { SQSBatchResponse, SQSEvent } from 'aws-lambda';
export declare function handler(event: SQSEvent): Promise<SQSBatchResponse>;
