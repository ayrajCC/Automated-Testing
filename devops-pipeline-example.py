#!/usr/bin/env python3
"""
CXone DevOps Pipeline Automation for Healthcare Telephony Applications
This script automates the deployment pipeline for CXone telephony scripts and configurations.
"""

import os
import sys
import json
import argparse
import requests
import logging
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cxone_pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("CXonePipeline")

class CXoneDeploymentPipeline:
    """
    Manages the deployment pipeline for CXone telephony scripts and configurations.
    Handles the process of validating, testing, and deploying CXone scripts and
    integration configurations across development, staging, and production environments.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the deployment pipeline with configuration.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.api_base_url = self.config.get('api_base_url')
        self.api_key = os.environ.get('CXONE_API_KEY') or self.config.get('api_key')
        
        if not self.api_key:
            raise ValueError("CXONE_API_KEY environment variable or api_key in config is required")
            
        logger.info(f"Initialized CXone deployment pipeline with config from {config_path}")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise
            
    def _api_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make an API request to the CXone API.
        
        Args:
            endpoint: API endpoint to call
            method: HTTP method (GET, POST, PUT, DELETE)
            data: Request payload for POST/PUT requests
            
        Returns:
            API response as dictionary
        """
        url = f"{self.api_base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
            
    def validate_script(self, script_path: str) -> bool:
        """
        Validate a CXone script for syntax errors.
        
        Args:
            script_path: Path to the script file
            
        Returns:
            True if validation passes, False otherwise
        """
        logger.info(f"Validating script: {script_path}")
        
        try:
            with open(script_path, 'r') as file:
                script_content = file.read()
                
            # Call validation API
            response = self._api_request(
                'scripts/validate', 
                method='POST',
                data={'content': script_content}
            )
            
            if response.get('valid', False):
                logger.info(f"Script validation successful: {script_path}")
                return True
            else:
                errors = response.get('errors', [])
                for error in errors:
                    logger.error(f"Validation error: {error.get('message')} at line {error.get('line')}")
                return False
                
        except Exception as e:
            logger.error(f"Script validation failed: {str(e)}")
            return False
            
    def run_tests(self, test_suite_path: str) -> bool:
        """
        Run automated tests against a script or configuration.
        
        Args:
            test_suite_path: Path to the test suite configuration
            
        Returns:
            True if all tests pass, False otherwise
        """
        logger.info(f"Running test suite: {test_suite_path}")
        
        try:
            with open(test_suite_path, 'r') as file:
                test_suite = yaml.safe_load(file)
                
            # Run tests through API
            response = self._api_request(
                'tests/run',
                method='POST',
                data=test_suite
            )
            
            total_tests = response.get('total', 0)
            passed_tests = response.get('passed', 0)
            
            logger.info(f"Tests completed: {passed_tests}/{total_tests} passed")
            
            # Log test failures
            failures = response.get('failures', [])
            for failure in failures:
                logger.error(f"Test failure: {failure.get('name')} - {failure.get('message')}")
                
            return passed_tests == total_tests
            
        except Exception as e:
            logger.error(f"Test execution failed: {str(e)}")
            return False
            
    def deploy_to_environment(self, script_path: str, environment: str) -> bool:
        """
        Deploy a script to the specified environment.
        
        Args:
            script_path: Path to the script file
            environment: Target environment (dev, staging, prod)
            
        Returns:
            True if deployment succeeds, False otherwise
        """
        logger.info(f"Deploying script to {environment}: {script_path}")
        
        try:
            with open(script_path, 'r') as file:
                script_content = file.read()
                
            # Get environment-specific configuration
            env_config = self.config.get('environments', {}).get(environment, {})
            if not env_config:
                logger.error(f"Environment configuration not found for: {environment}")
                return False
                
            # Prepare deployment payload
            deployment = {
                'scriptContent': script_content,
                'environment': environment,
                'businessUnitId': env_config.get('business_unit_id'),
                'scriptName': os.path.basename(script_path).split('.')[0],
                'description': f"Deployed by pipeline on {datetime.now().isoformat()}"
            }
            
            # Call deployment API
            response = self._api_request(
                'scripts/deploy',
                method='POST',
                data=deployment
            )
            
            deployment_id = response.get('deploymentId')
            if deployment_id:
                logger.info(f"Deployment successful. Deployment ID: {deployment_id}")
                return True
            else:
                logger.error(f"Deployment failed: {response.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            return False
            
    def run_pipeline(self, script_path: str, environment: str, skip_tests: bool = False) -> bool:
        """
        Run the complete deployment pipeline for a script.
        
        Args:
            script_path: Path to the script file
            environment: Target environment (dev, staging, prod)
            skip_tests: Whether to skip running tests
            
        Returns:
            True if pipeline succeeds, False otherwise
        """
        logger.info(f"Starting deployment pipeline for {script_path} to {environment}")
        
        # Step 1: Validate script
        if not self.validate_script(script_path):
            logger.error("Pipeline failed at validation stage")
            return False
            
        # Step 2: Run tests (if not skipped)
        if not skip_tests:
            test_suite_path = os.path.join(
                os.path.dirname(script_path),
                'tests',
                f"{os.path.basename(script_path).split('.')[0]}_tests.yml"
            )
            
            if os.path.exists(test_suite_path):
                if not self.run_tests(test_suite_path):
                    logger.error("Pipeline failed at testing stage")
                    return False
            else:
                logger.warning(f"No test suite found at {test_suite_path}, skipping tests")
                
        # Step 3: Deploy to environment
        if not self.deploy_to_environment(script_path, environment):
            logger.error("Pipeline failed at deployment stage")
            return False
            
        logger.info(f"Pipeline completed successfully for {script_path} to {environment}")
        return True


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='CXone Deployment Pipeline')
    parser.add_argument('--config', required=True, help='Path to configuration YAML file')
    parser.add_argument('--script', required=True, help='Path to CXone script file')
    parser.add_argument('--environment', required=True, choices=['dev', 'staging', 'prod'], 
                        help='Target environment')
    parser.add_argument('--skip-tests', action='store_true', help='Skip running tests')
    
    args = parser.parse_args()
    
    try:
        pipeline = CXoneDeploymentPipeline(args.config)
        success = pipeline.run_pipeline(args.script, args.environment, args.skip_tests)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
