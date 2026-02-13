"""
AWS Cost Monitor for SageMaker Resources

Track and optimize AWS costs for ML workloads.
Essential for staying within budget during development.

Author: Vahant
"""

import boto3
from datetime import datetime, timedelta
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AWSCostMonitor:
    """
    Monitor and track AWS costs for SageMaker resources.

    Features:
    - Real-time endpoint cost tracking
    - Training job cost analysis
    - Budget alerts
    - Cost optimization recommendations
    """

    # SageMaker instance pricing (us-east-1, on-demand)
    # Updated as of 2024 - verify current pricing
    INSTANCE_PRICING = {
        # Training instances
        'ml.m5.large': 0.115,
        'ml.m5.xlarge': 0.23,
        'ml.m5.2xlarge': 0.461,
        'ml.m5.4xlarge': 0.922,
        'ml.c5.xlarge': 0.204,
        'ml.c5.2xlarge': 0.408,
        'ml.p3.2xlarge': 3.825,  # GPU
        'ml.p3.8xlarge': 14.688,  # GPU

        # Inference instances
        'ml.t2.medium': 0.056,
        'ml.t2.large': 0.111,
        'ml.t3.medium': 0.050,
        'ml.m5.large': 0.115,
        'ml.c5.large': 0.102,

        # Serverless
        'serverless': 0.00001667  # per second per GB memory
    }

    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize cost monitor.

        Args:
            region: AWS region
        """
        self.region = region
        self.sagemaker_client = boto3.client('sagemaker', region_name=region)
        self.ce_client = boto3.client('ce', region_name=region)

        logger.info(f"Cost Monitor initialized for region: {region}")

    def get_active_endpoints(self) -> List[Dict]:
        """
        Get all active SageMaker endpoints and their costs.

        Returns:
            List of endpoints with cost information
        """
        response = self.sagemaker_client.list_endpoints(
            StatusEquals='InService'
        )

        endpoints = []
        for endpoint in response.get('Endpoints', []):
            endpoint_name = endpoint['EndpointName']
            details = self._get_endpoint_details(endpoint_name)
            endpoints.append(details)

        return endpoints

    def _get_endpoint_details(self, endpoint_name: str) -> Dict:
        """Get detailed information about an endpoint"""
        response = self.sagemaker_client.describe_endpoint(
            EndpointName=endpoint_name
        )

        config_response = self.sagemaker_client.describe_endpoint_config(
            EndpointConfigName=response['EndpointConfigName']
        )

        # Calculate cost
        production_variants = config_response.get('ProductionVariants', [])
        total_hourly_cost = 0

        for variant in production_variants:
            instance_type = variant.get('InstanceType', 'ml.t2.medium')
            instance_count = variant.get('InitialInstanceCount', 1)
            hourly_rate = self.INSTANCE_PRICING.get(instance_type, 0.1)
            total_hourly_cost += hourly_rate * instance_count

        # Calculate runtime
        creation_time = response.get('CreationTime')
        if creation_time:
            runtime_hours = ((datetime.now(creation_time.tzinfo)
                              - creation_time).total_seconds() / 3600)
        else:
            runtime_hours = 0

        return {
            'endpoint_name': endpoint_name,
            'status': response.get('EndpointStatus'),
            'creation_time': str(creation_time),
            'instance_type': production_variants[0].get('InstanceType') if production_variants else 'unknown',
            'instance_count': production_variants[0].get('InitialInstanceCount', 1) if production_variants else 1,
            'hourly_cost_usd': round(total_hourly_cost, 4),
            'runtime_hours': round(runtime_hours, 2),
            'total_cost_usd': round(total_hourly_cost * runtime_hours, 2)
        }

    def get_recent_training_jobs(self, days: int = 7) -> List[Dict]:
        """
        Get recent training jobs and their costs.

        Args:
            days: Number of days to look back

        Returns:
            List of training jobs with cost information
        """
        start_time = datetime.now() - timedelta(days=days)

        response = self.sagemaker_client.list_training_jobs(
            CreationTimeAfter=start_time,
            SortBy='CreationTime',
            SortOrder='Descending'
        )

        jobs = []
        for job in response.get('TrainingJobSummaries', []):
            job_details = self._get_training_job_details(
                job['TrainingJobName'])
            jobs.append(job_details)

        return jobs

    def _get_training_job_details(self, job_name: str) -> Dict:
        """Get detailed information about a training job"""
        response = self.sagemaker_client.describe_training_job(
            TrainingJobName=job_name
        )

        # Calculate cost
        instance_type = response.get(
            'ResourceConfig', {}).get(
            'InstanceType', 'ml.m5.large')
        instance_count = response.get(
            'ResourceConfig', {}).get(
            'InstanceCount', 1)

        # Training duration
        start_time = response.get('TrainingStartTime')
        end_time = response.get('TrainingEndTime')

        if start_time and end_time:
            duration_seconds = (end_time - start_time).total_seconds()
            duration_hours = duration_seconds / 3600
        else:
            duration_hours = 0

        hourly_rate = self.INSTANCE_PRICING.get(instance_type, 0.115)
        total_cost = hourly_rate * instance_count * duration_hours

        return {
            'job_name': job_name,
            'status': response.get('TrainingJobStatus'),
            'instance_type': instance_type,
            'instance_count': instance_count,
            'duration_minutes': round(duration_hours * 60, 2),
            'hourly_rate_usd': hourly_rate,
            'total_cost_usd': round(total_cost, 4),
            'creation_time': str(response.get('CreationTime'))
        }

    def get_cost_summary(self, days: int = 30) -> Dict:
        """
        Get comprehensive cost summary for SageMaker.

        Args:
            days: Number of days to analyze

        Returns:
            Cost summary dictionary
        """
        # Get active endpoints
        endpoints = self.get_active_endpoints()
        endpoint_cost = sum(e['total_cost_usd'] for e in endpoints)

        # Get training jobs
        training_jobs = self.get_recent_training_jobs(days=days)
        training_cost = sum(j['total_cost_usd'] for j in training_jobs)

        # Calculate projected monthly cost
        daily_endpoint_cost = sum(e['hourly_cost_usd'] * 24 for e in endpoints)
        monthly_projection = daily_endpoint_cost * 30

        return {
            'period_days': days,
            'active_endpoints': len(endpoints),
            'endpoint_costs': {
                'current_total_usd': round(endpoint_cost, 2),
                'hourly_rate_usd': round(sum(e['hourly_cost_usd'] for e in endpoints), 4),
                'daily_rate_usd': round(daily_endpoint_cost, 2),
                'monthly_projection_usd': round(monthly_projection, 2)
            },
            'training_costs': {
                'jobs_count': len(training_jobs),
                'total_usd': round(training_cost, 2)
            },
            'total_cost_usd': round(endpoint_cost + training_cost, 2),
            'endpoints': endpoints,
            'recent_training_jobs': training_jobs[:5]  # Last 5 jobs
        }

    def get_cost_optimization_recommendations(self) -> List[Dict]:
        """
        Generate cost optimization recommendations.

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check for active endpoints
        endpoints = self.get_active_endpoints()

        for endpoint in endpoints:
            # Long-running endpoint
            if endpoint['runtime_hours'] > 24:
                recommendations.append({
                    'type': 'warning',
                    'resource': endpoint['endpoint_name'],
                    'issue': f"Endpoint running for {endpoint['runtime_hours']:.1f} hours",
                    'recommendation': 'Delete endpoint when not in use to save costs',
                    'potential_savings_usd': round(endpoint['hourly_cost_usd'] * 24 * 30, 2),
                    'action': f"sagemaker_client.delete_endpoint(EndpointName='{endpoint['endpoint_name']}')"
                })

            # Oversized instance
            if endpoint['instance_type'] in [
                    'ml.m5.xlarge', 'ml.m5.2xlarge', 'ml.m5.4xlarge']:
                recommendations.append({
                    'type': 'optimization',
                    'resource': endpoint['endpoint_name'],
                    'issue': f"Using {endpoint['instance_type']} which may be oversized",
                    'recommendation': 'Consider ml.t2.medium or ml.t3.medium for low-traffic endpoints',
                    'potential_savings_usd': round((endpoint['hourly_cost_usd'] - 0.05) * 24 * 30, 2)
                })

        # General recommendations
        recommendations.append({
            'type': 'best_practice',
            'resource': 'all',
            'issue': 'General cost optimization',
            'recommendation': 'Use batch transform for batch predictions instead of real-time endpoints',
            'potential_savings_usd': 'Variable based on usage pattern'
        })

        recommendations.append({
            'type': 'best_practice',
            'resource': 'all',
            'issue': 'Development best practice',
            'recommendation': 'Always delete endpoints after testing. Use: delete_endpoint()',
            'potential_savings_usd': 'Up to $40/month per endpoint'
        })

        return recommendations

    def cleanup_idle_endpoints(self,
                               max_idle_hours: float = 24,
                               dry_run: bool = True) -> List[str]:
        """
        Identify and optionally delete idle endpoints.

        Args:
            max_idle_hours: Maximum hours before endpoint is considered idle
            dry_run: If True, only report without deleting

        Returns:
            List of endpoints that were/would be deleted
        """
        endpoints = self.get_active_endpoints()
        idle_endpoints = [
            e for e in endpoints if e['runtime_hours'] > max_idle_hours]

        deleted = []

        for endpoint in idle_endpoints:
            endpoint_name = endpoint['endpoint_name']

            if dry_run:
                logger.info(f"[DRY RUN] Would delete: {endpoint_name} "
                            f"(running {endpoint['runtime_hours']:.1f} hours, "
                            f"cost: ${endpoint['total_cost_usd']})")
            else:
                try:
                    self.sagemaker_client.delete_endpoint(
                        EndpointName=endpoint_name)
                    logger.info(f"Deleted endpoint: {endpoint_name}")
                    deleted.append(endpoint_name)
                except Exception as e:
                    logger.error(f"Failed to delete {endpoint_name}: {e}")

        return deleted


def print_cost_report(region: str = 'us-east-1'):
    """Generate and print a cost report"""
    monitor = AWSCostMonitor(region=region)

    print("\n" + "=" * 60)
    print("AWS SAGEMAKER COST REPORT")
    print("=" * 60)

    summary = monitor.get_cost_summary(days=7)

    print(f"\n📊 Summary (Last {summary['period_days']} days)")
    print("-" * 40)
    print(f"Active Endpoints: {summary['active_endpoints']}")
    print(f"Training Jobs: {summary['training_costs']['jobs_count']}")
    print(f"Total Cost: ${summary['total_cost_usd']}")

    print("\n💰 Endpoint Costs")
    print("-" * 40)
    ec = summary['endpoint_costs']
    print(f"Current Total: ${ec['current_total_usd']}")
    print(f"Hourly Rate: ${ec['hourly_rate_usd']}")
    print(f"Daily Rate: ${ec['daily_rate_usd']}")
    print(f"Monthly Projection: ${ec['monthly_projection_usd']}")

    print("\n🏋️ Training Costs")
    print("-" * 40)
    tc = summary['training_costs']
    print(f"Jobs Count: {tc['jobs_count']}")
    print(f"Total: ${tc['total_usd']}")

    print("\n💡 Recommendations")
    print("-" * 40)
    recommendations = monitor.get_cost_optimization_recommendations()
    for rec in recommendations[:5]:
        print(f"[{rec['type'].upper()}] {rec['recommendation']}")
        if isinstance(rec.get('potential_savings_usd'), (int, float)):
            print(
                f"   Potential savings: ${rec['potential_savings_usd']}/month")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_cost_report()
