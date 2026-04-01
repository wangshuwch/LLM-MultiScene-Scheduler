from dataclasses import dataclass
from typing import Dict, List, Optional
import os
import json
from datetime import datetime
from .monitoring import SimulationResult

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
    HAS_VISUALIZATION = True
    
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 12
except ImportError:
    HAS_VISUALIZATION = False
    plt = None
    sns = None
    np = None


@dataclass
class VisualizationConfig:
    output_dir: str = "simulation_results"
    dpi: int = 150
    figure_format: str = "png"
    show_grid: bool = True


class ReportGenerator:
    def __init__(self, config: Optional[VisualizationConfig] = None):
        self.config = config or VisualizationConfig()
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        os.makedirs(self.config.output_dir, exist_ok=True)

    def _get_output_path(self, filename: str) -> str:
        return os.path.join(self.config.output_dir, filename)

    def plot_response_time_distribution(self, result: SimulationResult, filename: str = "response_time_distribution.png"):
        if not HAS_VISUALIZATION:
            print("Warning: matplotlib/seaborn not installed, skipping chart generation")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Response Time Analysis - {result.scenario_name}', fontsize=16)
        
        times = [r.total_time_ms for r in result.request_records if r.total_time_ms > 0]
        
        if times:
            axes[0, 0].hist(times, bins=50, alpha=0.7, color='skyblue', edgecolor='black')
            axes[0, 0].axvline(result.overall_response_time.avg_ms, color='red', linestyle='--', label=f'Avg: {result.overall_response_time.avg_ms:.1f}ms')
            axes[0, 0].axvline(result.overall_response_time.p95_ms, color='orange', linestyle='--', label=f'P95: {result.overall_response_time.p95_ms:.1f}ms')
            axes[0, 0].axvline(result.overall_response_time.p99_ms, color='purple', linestyle='--', label=f'P99: {result.overall_response_time.p99_ms:.1f}ms')
            axes[0, 0].set_title('Response Time Distribution')
            axes[0, 0].set_xlabel('Response Time (ms)')
            axes[0, 0].set_ylabel('Count')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            axes[0, 1].boxplot(times, vert=True)
            axes[0, 1].set_title('Response Time Box Plot')
            axes[0, 1].set_ylabel('Response Time (ms)')
            axes[0, 1].grid(True, alpha=0.3)
            
            percentiles = [50, 75, 90, 95, 99]
            percentile_values = [
                result.overall_response_time.p50_ms,
                result.overall_response_time.p75_ms,
                result.overall_response_time.p95_ms * 0.9,
                result.overall_response_time.p95_ms,
                result.overall_response_time.p99_ms
            ]
            axes[1, 0].bar([f'P{p}' for p in percentiles], percentile_values, color='steelblue', alpha=0.7)
            axes[1, 0].set_title('Response Time Percentiles')
            axes[1, 0].set_ylabel('Response Time (ms)')
            axes[1, 0].grid(True, alpha=0.3, axis='y')
            
            scene_times = {}
            for scene_id, metrics in result.scene_metrics.items():
                scene_times[scene_id] = metrics.response_time.avg_ms
            
            if scene_times:
                axes[1, 1].bar(scene_times.keys(), scene_times.values(), color='coral', alpha=0.7)
                axes[1, 1].set_title('Average Response Time by Scene')
                axes[1, 1].set_xlabel('Scene ID')
                axes[1, 1].set_ylabel('Average Response Time (ms)')
                axes[1, 1].tick_params(axis='x', rotation=45)
                axes[1, 1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(self._get_output_path(filename), dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        return self._get_output_path(filename)

    def plot_success_rate(self, result: SimulationResult, filename: str = "success_rate.png"):
        if not HAS_VISUALIZATION:
            print("Warning: matplotlib/seaborn not installed, skipping chart generation")
            return None
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f'Success Rate Analysis - {result.scenario_name}', fontsize=16)
        
        sr = result.overall_success_rate
        labels = ['Successful', 'Failed', 'Timeout']
        sizes = [sr.successful, sr.failed, sr.timeout]
        colors = ['#4CAF50', '#F44336', '#FF9800']
        
        axes[0].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        axes[0].set_title('Overall Request Status Distribution')
        
        scene_success_rates = {}
        for scene_id, metrics in result.scene_metrics.items():
            scene_success_rates[scene_id] = metrics.success_rate.success_rate * 100
        
        if scene_success_rates:
            scenes = list(scene_success_rates.keys())
            rates = list(scene_success_rates.values())
            bars = axes[1].bar(scenes, rates, color='seagreen', alpha=0.7)
            axes[1].set_title('Success Rate by Scene')
            axes[1].set_xlabel('Scene ID')
            axes[1].set_ylabel('Success Rate (%)')
            axes[1].set_ylim([0, 105])
            axes[1].tick_params(axis='x', rotation=45)
            axes[1].axhline(y=90, color='red', linestyle='--', label='90% Target')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3, axis='y')
            
            for bar, rate in zip(bars, rates):
                axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                            f'{rate:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(self._get_output_path(filename), dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        return self._get_output_path(filename)

    def plot_resource_utilization(self, result: SimulationResult, filename: str = "resource_utilization.png"):
        if not HAS_VISUALIZATION:
            print("Warning: matplotlib/seaborn not installed, skipping chart generation")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Resource Utilization - {result.scenario_name}', fontsize=16)
        
        if result.resource_history:
            timestamps = [m.timestamp for m in result.resource_history]
            start_time = timestamps[0] if timestamps else 0
            relative_times = [(t - start_time) / 60 for t in timestamps]
            
            cpu_util = [m.cpu_utilization * 100 for m in result.resource_history]
            mem_util = [m.memory_utilization * 100 for m in result.resource_history]
            
            if cpu_util:
                axes[0, 0].plot(relative_times, cpu_util, color='blue', label='CPU', linewidth=2)
                axes[0, 0].set_title('CPU Utilization Over Time')
                axes[0, 0].set_xlabel('Time (minutes)')
                axes[0, 0].set_ylabel('Utilization (%)')
                axes[0, 0].set_ylim([0, 105])
                axes[0, 0].legend()
                axes[0, 0].grid(True, alpha=0.3)
            
            if mem_util:
                axes[0, 1].plot(relative_times, mem_util, color='green', label='Memory', linewidth=2)
                axes[0, 1].set_title('Memory Utilization Over Time')
                axes[0, 1].set_xlabel('Time (minutes)')
                axes[0, 1].set_ylabel('Utilization (%)')
                axes[0, 1].set_ylim([0, 105])
                axes[0, 1].legend()
                axes[0, 1].grid(True, alpha=0.3)
            
            active_instances = [m.active_instances for m in result.resource_history]
            busy_instances = [m.busy_instances for m in result.resource_history]
            overloaded_instances = [m.overloaded_instances for m in result.resource_history]
            
            if active_instances:
                axes[1, 0].plot(relative_times, active_instances, label='Active', linewidth=2)
                axes[1, 0].plot(relative_times, busy_instances, label='Busy', linewidth=2)
                axes[1, 0].plot(relative_times, overloaded_instances, label='Overloaded', linewidth=2)
                axes[1, 0].set_title('Instance Status Over Time')
                axes[1, 0].set_xlabel('Time (minutes)')
                axes[1, 0].set_ylabel('Number of Instances')
                axes[1, 0].legend()
                axes[1, 0].grid(True, alpha=0.3)
            
            avg_cpu = np.mean(cpu_util) if cpu_util else 0
            avg_mem = np.mean(mem_util) if mem_util else 0
            max_cpu = np.max(cpu_util) if cpu_util else 0
            max_mem = np.max(mem_util) if mem_util else 0
            
            metrics = ['Avg CPU', 'Max CPU', 'Avg Mem', 'Max Mem']
            values = [avg_cpu, max_cpu, avg_mem, max_mem]
            colors = ['skyblue', 'steelblue', 'lightgreen', 'green']
            
            bars = axes[1, 1].bar(metrics, values, color=colors, alpha=0.7)
            axes[1, 1].set_title('Resource Summary')
            axes[1, 1].set_ylabel('Utilization (%)')
            axes[1, 1].set_ylim([0, 105])
            axes[1, 1].grid(True, alpha=0.3, axis='y')
            
            for bar, val in zip(bars, values):
                axes[1, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                               f'{val:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(self._get_output_path(filename), dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        return self._get_output_path(filename)

    def plot_throughput(self, result: SimulationResult, filename: str = "throughput.png"):
        if not HAS_VISUALIZATION:
            print("Warning: matplotlib/seaborn not installed, skipping chart generation")
            return None
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f'Throughput Analysis - {result.scenario_name}', fontsize=16)
        
        throughput = result.overall_throughput
        
        axes[0].bar(['Requests/sec', 'Tokens/sec'],
                   [throughput.requests_per_second, throughput.tokens_per_second / 1000],
                   color=['#2196F3', '#9C27B0'], alpha=0.7)
        axes[0].set_title('Average Throughput')
        axes[0].set_ylabel('Rate')
        axes[0].text(0, throughput.requests_per_second * 1.02,
                    f'{throughput.requests_per_second:.2f} req/s',
                    ha='center')
        axes[0].text(1, throughput.tokens_per_second / 1000 * 1.02,
                    f'{throughput.tokens_per_second/1000:.2f}K tokens/s',
                    ha='center')
        axes[0].grid(True, alpha=0.3, axis='y')
        
        scene_throughput = {}
        for scene_id, metrics in result.scene_metrics.items():
            scene_throughput[scene_id] = metrics.throughput.requests_per_second
        
        if scene_throughput:
            bars = axes[1].bar(scene_throughput.keys(), scene_throughput.values(), color='darkorange', alpha=0.7)
            axes[1].set_title('Throughput by Scene')
            axes[1].set_xlabel('Scene ID')
            axes[1].set_ylabel('Requests/Second')
            axes[1].tick_params(axis='x', rotation=45)
            axes[1].grid(True, alpha=0.3, axis='y')
            
            for bar, rate in zip(bars, scene_throughput.values()):
                axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.02,
                            f'{rate:.2f}', ha='center')
        
        plt.tight_layout()
        plt.savefig(self._get_output_path(filename), dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        return self._get_output_path(filename)

    def generate_all_charts(self, result: SimulationResult) -> Dict[str, str]:
        charts = {}
        charts['response_time'] = self.plot_response_time_distribution(result)
        charts['success_rate'] = self.plot_success_rate(result)
        charts['resource_utilization'] = self.plot_resource_utilization(result)
        charts['throughput'] = self.plot_throughput(result)
        return charts

    def generate_html_report(self, result: SimulationResult, charts: Dict[str, str]) -> str:
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Simulation Report - {result.scenario_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-left: 4px solid #2196F3;
            padding-left: 10px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .summary-card.success {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .summary-card.warning {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .summary-card.info {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}
        .summary-value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .chart-container {{
            margin: 30px 0;
            text-align: center;
        }}
        .chart-container img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .metadata {{
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Simulation Report</h1>
        <h2>{result.scenario_name}</h2>
        
        <div class="metadata">
            <strong>Scenario ID:</strong> {result.scenario_id}<br>
            <strong>Duration:</strong> {result.duration_seconds:.1f} seconds<br>
            <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <h2>Key Metrics Summary</h2>
        <div class="summary-grid">
            <div class="summary-card success">
                <div>Success Rate</div>
                <div class="summary-value">{result.overall_success_rate.success_rate*100:.1f}%</div>
                <div>{result.overall_success_rate.successful}/{result.overall_success_rate.total_requests}</div>
            </div>
            <div class="summary-card info">
                <div>Avg Response Time</div>
                <div class="summary-value">{result.overall_response_time.avg_ms:.1f}ms</div>
                <div>P95: {result.overall_response_time.p95_ms:.1f}ms</div>
            </div>
            <div class="summary-card warning">
                <div>Throughput</div>
                <div class="summary-value">{result.overall_throughput.requests_per_second:.1f}</div>
                <div>requests/second</div>
            </div>
            <div class="summary-card">
                <div>Total Requests</div>
                <div class="summary-value">{result.overall_success_rate.total_requests}</div>
                <div>processed</div>
            </div>
        </div>
        
        <h2>Charts</h2>
        
        <div class="chart-container">
            <h3>Response Time Distribution</h3>
            <img src="response_time_distribution.png" alt="Response Time Distribution">
        </div>
        
        <div class="chart-container">
            <h3>Success Rate</h3>
            <img src="success_rate.png" alt="Success Rate">
        </div>
        
        <div class="chart-container">
            <h3>Resource Utilization</h3>
            <img src="resource_utilization.png" alt="Resource Utilization">
        </div>
        
        <div class="chart-container">
            <h3>Throughput</h3>
            <img src="throughput.png" alt="Throughput">
        </div>
        
        <h2>Scene-wise Metrics</h2>
        <table>
            <tr>
                <th>Scene ID</th>
                <th>Total Requests</th>
                <th>Success Rate</th>
                <th>Avg Response (ms)</th>
                <th>P95 Response (ms)</th>
                <th>Throughput (req/s)</th>
            </tr>
"""
        
        for scene_id, metrics in result.scene_metrics.items():
            html_content += f"""
            <tr>
                <td>{scene_id}</td>
                <td>{metrics.success_rate.total_requests}</td>
                <td>{metrics.success_rate.success_rate*100:.1f}%</td>
                <td>{metrics.response_time.avg_ms:.1f}</td>
                <td>{metrics.response_time.p95_ms:.1f}</td>
                <td>{metrics.throughput.requests_per_second:.2f}</td>
            </tr>
"""
        
        html_content += """
        </table>
        
        <h2>Detailed Response Time Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Minimum</td>
                <td>{:.1f} ms</td>
            </tr>
            <tr>
                <td>Average</td>
                <td>{:.1f} ms</td>
            </tr>
            <tr>
                <td>P50 (Median)</td>
                <td>{:.1f} ms</td>
            </tr>
            <tr>
                <td>P75</td>
                <td>{:.1f} ms</td>
            </tr>
            <tr>
                <td>P95</td>
                <td>{:.1f} ms</td>
            </tr>
            <tr>
                <td>P99</td>
                <td>{:.1f} ms</td>
            </tr>
            <tr>
                <td>Maximum</td>
                <td>{:.1f} ms</td>
            </tr>
        </table>
    </div>
</body>
</html>
""".format(
            result.overall_response_time.min_ms,
            result.overall_response_time.avg_ms,
            result.overall_response_time.p50_ms,
            result.overall_response_time.p75_ms,
            result.overall_response_time.p95_ms,
            result.overall_response_time.p99_ms,
            result.overall_response_time.max_ms
        )
        
        report_path = self._get_output_path("report.html")
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return report_path

    def save_result_json(self, result: SimulationResult, filename: str = "result.json") -> str:
        result_dict = {
            "scenario_id": result.scenario_id,
            "scenario_name": result.scenario_name,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "duration_seconds": result.duration_seconds,
            "overall_response_time": {
                "avg_ms": result.overall_response_time.avg_ms,
                "p50_ms": result.overall_response_time.p50_ms,
                "p75_ms": result.overall_response_time.p75_ms,
                "p95_ms": result.overall_response_time.p95_ms,
                "p99_ms": result.overall_response_time.p99_ms,
                "max_ms": result.overall_response_time.max_ms,
                "min_ms": result.overall_response_time.min_ms,
                "count": result.overall_response_time.count
            },
            "overall_success_rate": {
                "total_requests": result.overall_success_rate.total_requests,
                "successful": result.overall_success_rate.successful,
                "failed": result.overall_success_rate.failed,
                "timeout": result.overall_success_rate.timeout,
                "success_rate": result.overall_success_rate.success_rate,
                "failure_rate": result.overall_success_rate.failure_rate
            },
            "overall_throughput": {
                "requests_per_second": result.overall_throughput.requests_per_second,
                "tokens_per_second": result.overall_throughput.tokens_per_second,
                "total_requests": result.overall_throughput.total_requests,
                "total_tokens": result.overall_throughput.total_tokens
            },
            "scene_metrics": {
                scene_id: {
                    "response_time": {
                        "avg_ms": m.response_time.avg_ms,
                        "p95_ms": m.response_time.p95_ms
                    },
                    "success_rate": m.success_rate.success_rate,
                    "throughput": m.throughput.requests_per_second
                }
                for scene_id, m in result.scene_metrics.items()
            }
        }
        
        json_path = self._get_output_path(filename)
        with open(json_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        return json_path

    def generate_full_report(self, result: SimulationResult) -> Dict[str, str]:
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        original_dir = self.config.output_dir
        self.config.output_dir = os.path.join(original_dir, result.scenario_id)
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        charts = self.generate_all_charts(result)
        html_report = self.generate_html_report(result, charts)
        json_result = self.save_result_json(result)
        
        self.config.output_dir = original_dir
        
        return {
            "charts": charts,
            "html_report": html_report,
            "json_result": json_result
        }
