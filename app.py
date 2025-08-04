from flask import Flask, request, jsonify
from flask_cors import CORS
from apify_client import ApifyClient
import os
from typing import Dict, List, Any
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for Node.js frontend requests

# Initialize the ApifyClient with your API token
# You can also set this as an environment variable for security
APIFY_TOKEN = os.getenv('APIFY_API_TOKEN', 'apify_api_fLz2QjEaS3anXjvBBXlwOOB6eYNUaN2krhlt')
client = ApifyClient(APIFY_TOKEN)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Indeed Scraper API is running',
        'version': '1.0.0'
    })

@app.route('/scrape', methods=['POST'])
def scrape_jobs():
    """
    Main endpoint to scrape Indeed jobs
    Expected JSON payload:
    {
        "position": "web developer",
        "country": "US", 
        "location": "San Francisco",
        "maxItems": 5
    }
    """
    try:
        # Get JSON data from request
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided'
            }), 400
        
        # Extract parameters with defaults
        position = data.get('position')
        country = data.get('country', 'US')
        location = data.get('location')
        max_items = data.get('maxItems', 10)
        
        # Validate required fields
        if not position:
            return jsonify({
                'status': 'error',
                'message': 'Position is required'
            }), 400
        
        if not location:
            return jsonify({
                'status': 'error',
                'message': 'Location is required'
            }), 400
        
        # Prepare the Actor input
        run_input = {
            "position": position,
            "country": country,
            "location": location,
            "maxItems": max_items,
        }
        
        logger.info(f"Starting scrape with input: {run_input}")
        
        # Run the Actor and wait for it to finish
        run = client.actor("misceres/indeed-scraper").call(run_input=run_input)
        
        # Fetch Actor results from the run's dataset
        jobs = []
        dataset_id = run["defaultDatasetId"]
        
        logger.info(f"Dataset ID: {dataset_id}")
        
        for item in client.dataset(dataset_id).iterate_items():
            jobs.append(item)
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully scraped {len(jobs)} jobs',
            'data': {
                'jobs': jobs,
                'count': len(jobs),
                'dataset_url': f"https://console.apify.com/storage/datasets/{dataset_id}",
                'search_params': run_input
            }
        })
        
    except Exception as e:
        logger.error(f"Error in scrape_jobs: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Scraping failed: {str(e)}'
        }), 500

@app.route('/scrape/batch', methods=['POST'])
def scrape_jobs_batch():
    """
    Batch endpoint to scrape multiple job searches
    Expected JSON payload:
    {
        "searches": [
            {
                "position": "web developer",
                "country": "US",
                "location": "San Francisco",
                "maxItems": 5
            },
            {
                "position": "python developer", 
                "country": "US",
                "location": "New York",
                "maxItems": 3
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'searches' not in data:
            return jsonify({
                'status': 'error',
                'message': 'searches array is required'
            }), 400
        
        searches = data['searches']
        if not isinstance(searches, list):
            return jsonify({
                'status': 'error',
                'message': 'searches must be an array'
            }), 400
        
        batch_results = []
        
        for i, search in enumerate(searches):
            try:
                # Validate each search
                position = search.get('position')
                if not position:
                    batch_results.append({
                        'index': i,
                        'status': 'error',
                        'message': 'Position is required',
                        'data': None
                    })
                    continue
                
                location = search.get('location')
                if not location:
                    batch_results.append({
                        'index': i,
                        'status': 'error', 
                        'message': 'Location is required',
                        'data': None
                    })
                    continue
                
                run_input = {
                    "position": position,
                    "country": search.get('country', 'US'),
                    "location": location,
                    "maxItems": search.get('maxItems', 10),
                }
                
                # Run the scraper
                run = client.actor("misceres/indeed-scraper").call(run_input=run_input)
                
                # Collect results
                jobs = []
                for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                    jobs.append(item)
                
                batch_results.append({
                    'index': i,
                    'status': 'success',
                    'message': f'Successfully scraped {len(jobs)} jobs',
                    'data': {
                        'jobs': jobs,
                        'count': len(jobs),
                        'search_params': run_input
                    }
                })
                
            except Exception as e:
                batch_results.append({
                    'index': i,
                    'status': 'error',
                    'message': f'Scraping failed: {str(e)}',
                    'data': None
                })
        
        # Calculate summary
        successful_searches = len([r for r in batch_results if r['status'] == 'success'])
        total_jobs = sum([r['data']['count'] for r in batch_results if r['data']])
        
        return jsonify({
            'status': 'success',
            'message': f'Batch processing completed: {successful_searches}/{len(searches)} successful',
            'data': {
                'results': batch_results,
                'summary': {
                    'total_searches': len(searches),
                    'successful_searches': successful_searches,
                    'failed_searches': len(searches) - successful_searches,
                    'total_jobs_found': total_jobs
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error in batch scraping: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Batch scraping failed: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'status': 'error',
        'message': 'Method not allowed'
    }), 405

if __name__ == '__main__':
    # For development
    app.run(debug=True, host='0.0.0.0', port=5001)