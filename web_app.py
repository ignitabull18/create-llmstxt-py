#!/usr/bin/env python3
"""
Web interface for the llms.txt generator.
Provides a simple API and web UI for generating llms.txt files.
"""

import os
import json
import logging
from typing import Dict, Any
from flask import Flask, request, jsonify, render_template_string, send_file
from werkzeug.exceptions import BadRequest
import tempfile
import shutil
from termcolor import colored
import threading
import time
import uuid

# Import the generator class
import sys
import os
sys.path.append(os.path.dirname(__file__))

# Import using the actual filename
import importlib.util
spec = importlib.util.spec_from_file_location("generate_llmstxt", "generate-llmstxt.py")
generate_llmstxt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_llmstxt)
FirecrawlLLMsTextGenerator = generate_llmstxt.FirecrawlLLMsTextGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Store for active jobs
ACTIVE_JOBS = {}
COMPLETED_JOBS = {}

class JobProcessor:
    """Handle background job processing."""
    
    def __init__(self):
        self.generator = None
        self._init_generator()
    
    def _init_generator(self):
        """Initialize the generator with API keys."""
        firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        
        if not firecrawl_key or not openai_key:
            print(colored("⚠️  API keys not found in environment variables", "yellow"))
            print(colored("Please set FIRECRAWL_API_KEY and OPENAI_API_KEY", "yellow"))
            return
        
        try:
            self.generator = FirecrawlLLMsTextGenerator(firecrawl_key, openai_key)
            print(colored("✅ Generator initialized successfully", "green"))
        except Exception as e:
            print(colored(f"❌ Failed to initialize generator: {e}", "red"))
    
    def process_job(self, job_id: str, url: str, max_urls: int = 20, include_full_text: bool = True):
        """Process a job in the background."""
        try:
            print(colored(f"🚀 Starting job {job_id} for {url}", "cyan"))
            ACTIVE_JOBS[job_id] = {
                "url": url,
                "status": "processing",
                "progress": "Initializing...",
                "start_time": time.time()
            }
            
            if not self.generator:
                raise Exception("Generator not initialized - check API keys")
            
            # Update progress
            ACTIVE_JOBS[job_id]["progress"] = "Mapping website..."
            
            result = self.generator.generate_llmstxt(url, max_urls, include_full_text)
            
            # Create temporary files
            temp_dir = tempfile.mkdtemp()
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace("www.", "")
            
            llmstxt_path = os.path.join(temp_dir, f"{domain}-llms.txt")
            llms_fulltxt_path = os.path.join(temp_dir, f"{domain}-llms-full.txt")
            
            # Write files
            with open(llmstxt_path, "w", encoding="utf-8") as f:
                f.write(result["llmstxt"])
            
            if include_full_text:
                with open(llms_fulltxt_path, "w", encoding="utf-8") as f:
                    f.write(result["llms_fulltxt"])
            
            # Move to completed jobs
            COMPLETED_JOBS[job_id] = {
                "url": url,
                "status": "completed",
                "result": result,
                "files": {
                    "llmstxt": llmstxt_path,
                    "llms_fulltxt": llms_fulltxt_path if include_full_text else None
                },
                "completion_time": time.time(),
                "temp_dir": temp_dir
            }
            
            if job_id in ACTIVE_JOBS:
                del ACTIVE_JOBS[job_id]
            
            print(colored(f"✅ Job {job_id} completed successfully", "green"))
            
        except Exception as e:
            error_msg = str(e)
            print(colored(f"❌ Job {job_id} failed: {error_msg}", "red"))
            
            COMPLETED_JOBS[job_id] = {
                "url": url,
                "status": "failed",
                "error": error_msg,
                "completion_time": time.time()
            }
            
            if job_id in ACTIVE_JOBS:
                del ACTIVE_JOBS[job_id]

job_processor = JobProcessor()

# HTML templates
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLMs.txt Generator</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: 600; color: #555; }
        input, select { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 5px; font-size: 16px; }
        input:focus, select:focus { outline: none; border-color: #007cba; }
        button { background-color: #007cba; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { background-color: #005a87; }
        button:disabled { background-color: #ccc; cursor: not-allowed; }
        .status { margin-top: 20px; padding: 15px; border-radius: 5px; display: none; }
        .status.processing { background-color: #fff3cd; border: 1px solid #ffeaa7; }
        .status.completed { background-color: #d4edda; border: 1px solid #c3e6cb; }
        .status.failed { background-color: #f8d7da; border: 1px solid #f5c6cb; }
        .download-links { margin-top: 15px; }
        .download-links a { display: inline-block; margin-right: 15px; color: #007cba; text-decoration: none; font-weight: 600; }
        .download-links a:hover { text-decoration: underline; }
        .example { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px; }
        .example h3 { margin-top: 0; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 LLMs.txt Generator</h1>
        <p style="text-align: center; color: #666; margin-bottom: 30px;">
            Generate llms.txt files for any website using Firecrawl and OpenAI
        </p>
        
        <form id="generatorForm">
            <div class="form-group">
                <label for="url">Website URL:</label>
                <input type="url" id="url" name="url" placeholder="https://example.com" required>
            </div>
            
            <div class="form-group">
                <label for="maxUrls">Max URLs to process:</label>
                <select id="maxUrls" name="maxUrls">
                    <option value="10">10 URLs</option>
                    <option value="20" selected>20 URLs</option>
                    <option value="50">50 URLs</option>
                    <option value="100">100 URLs</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" id="includeFullText" name="includeFullText" checked>
                    Generate llms-full.txt (includes full page content)
                </label>
            </div>
            
            <button type="submit" id="submitBtn">Generate LLMs.txt</button>
        </form>
        
        <div id="status" class="status">
            <div id="statusContent"></div>
        </div>
        
        <div class="example">
            <h3>What is llms.txt?</h3>
            <p><strong>llms.txt</strong> is a standardized format for making website content more accessible to Large Language Models (LLMs). This tool generates:</p>
            <ul>
                <li><strong>llms.txt</strong>: A concise index of all pages with titles and descriptions</li>
                <li><strong>llms-full.txt</strong>: Complete content of all pages for comprehensive access</li>
            </ul>
        </div>
    </div>

    <script>
        let currentJobId = null;
        let pollInterval = null;

        document.getElementById('generatorForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const data = {
                url: formData.get('url'),
                max_urls: parseInt(formData.get('maxUrls')),
                include_full_text: formData.get('includeFullText') === 'on'
            };
            
            try {
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').textContent = 'Starting...';
                
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    currentJobId = result.job_id;
                    showStatus('processing', 'Job started! Processing website...');
                    startPolling();
                } else {
                    showStatus('failed', result.error || 'Failed to start job');
                    resetButton();
                }
                
            } catch (error) {
                showStatus('failed', 'Network error: ' + error.message);
                resetButton();
            }
        });

        function startPolling() {
            pollInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/status/${currentJobId}`);
                    const status = await response.json();
                    
                    if (status.status === 'processing') {
                        showStatus('processing', `Processing... ${status.progress || 'Working...'}`);
                    } else if (status.status === 'completed') {
                        showStatus('completed', 
                            `✅ Completed! Processed ${status.result.num_urls_processed} URLs.`,
                            currentJobId
                        );
                        stopPolling();
                        resetButton();
                    } else if (status.status === 'failed') {
                        showStatus('failed', `❌ Failed: ${status.error}`);
                        stopPolling();
                        resetButton();
                    }
                } catch (error) {
                    console.error('Polling error:', error);
                }
            }, 2000);
        }

        function stopPolling() {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        }

        function showStatus(type, message, jobId = null) {
            const statusDiv = document.getElementById('status');
            const contentDiv = document.getElementById('statusContent');
            
            statusDiv.className = `status ${type}`;
            statusDiv.style.display = 'block';
            
            let content = message;
            if (jobId && type === 'completed') {
                content += `
                    <div class="download-links">
                        <a href="/api/download/${jobId}/llmstxt" target="_blank">📄 Download llms.txt</a>
                        <a href="/api/download/${jobId}/llms_fulltxt" target="_blank">📚 Download llms-full.txt</a>
                    </div>
                `;
            }
            
            contentDiv.innerHTML = content;
        }

        function resetButton() {
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('submitBtn').textContent = 'Generate LLMs.txt';
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', stopPolling);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    """Home page with form."""
    return render_template_string(HOME_TEMPLATE)

@app.route('/api/generate', methods=['POST'])
def generate():
    """Start a new generation job."""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            raise BadRequest("URL is required")
        
        url = data['url']
        max_urls = data.get('max_urls', 20)
        include_full_text = data.get('include_full_text', True)
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Start background job
        thread = threading.Thread(
            target=job_processor.process_job,
            args=(job_id, url, max_urls, include_full_text)
        )
        thread.daemon = True
        thread.start()
        
        print(colored(f"🚀 Started job {job_id} for {url}", "cyan"))
        
        return jsonify({
            "job_id": job_id,
            "status": "started",
            "message": "Job started successfully"
        })
        
    except Exception as e:
        logger.error(f"Error starting job: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status."""
    if job_id in ACTIVE_JOBS:
        return jsonify(ACTIVE_JOBS[job_id])
    elif job_id in COMPLETED_JOBS:
        job = COMPLETED_JOBS[job_id].copy()
        # Remove file paths from public response
        if 'files' in job:
            del job['files']
        if 'temp_dir' in job:
            del job['temp_dir']
        return jsonify(job)
    else:
        return jsonify({"error": "Job not found"}), 404

@app.route('/api/download/<job_id>/<file_type>')
def download_file(job_id, file_type):
    """Download generated files."""
    if job_id not in COMPLETED_JOBS:
        return jsonify({"error": "Job not found"}), 404
    
    job = COMPLETED_JOBS[job_id]
    if job["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400
    
    files = job.get("files", {})
    
    if file_type == "llmstxt" and files.get("llmstxt"):
        return send_file(files["llmstxt"], as_attachment=True)
    elif file_type == "llms_fulltxt" and files.get("llms_fulltxt"):
        return send_file(files["llms_fulltxt"], as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "generator_ready": job_processor.generator is not None,
        "active_jobs": len(ACTIVE_JOBS),
        "completed_jobs": len(COMPLETED_JOBS)
    })

# Cleanup old jobs periodically
def cleanup_old_jobs():
    """Clean up old completed jobs."""
    cutoff_time = time.time() - 3600  # 1 hour ago
    
    jobs_to_remove = []
    for job_id, job in COMPLETED_JOBS.items():
        if job.get("completion_time", 0) < cutoff_time:
            # Clean up temp directory
            if "temp_dir" in job:
                try:
                    shutil.rmtree(job["temp_dir"])
                except:
                    pass
            jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del COMPLETED_JOBS[job_id]
    
    # Schedule next cleanup
    threading.Timer(1800, cleanup_old_jobs).start()  # 30 minutes

# Start cleanup timer
cleanup_old_jobs()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(colored(f"🚀 Starting LLMs.txt Generator Web App on port {port}", "green"))
    print(colored("📝 Make sure to set FIRECRAWL_API_KEY and OPENAI_API_KEY environment variables", "yellow"))
    
    app.run(host='0.0.0.0', port=port, debug=False) 