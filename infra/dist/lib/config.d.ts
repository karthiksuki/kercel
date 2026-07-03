export interface KercelStageConfig {
    readonly stage: string;
    readonly instanceType: string;
    readonly minCapacity: number;
    readonly maxCapacity: number;
    readonly desiredCapacity: number;
}
export declare function getStageConfig(stage: string): KercelStageConfig;
