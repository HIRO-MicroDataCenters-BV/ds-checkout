# Checkout Service

A FastAPI-based microservice for temporarily storing and retrieving data checkout orders. This service provides a simple REST API for managing checkout orders with automatic expiration using Redis as the backend storage.

## Overview

The Checkout Service is designed to handle temporary storage of data checkout orders in JSON-LD format. It accepts orders, stores them with a configurable TTL (Time To Live), and provides retrieval functionality using UUID-based order identifiers.

### Features

- **Temporary Order Storage**: Store checkout orders with configurable expiration times
- **JSON-LD Support**: Accepts and validates JSON-LD formatted data with DCAT vocabulary
- **UUID-based Identification**: Each order gets a unique UUID for secure retrieval
- **Redis Backend**: Uses Redis for high-performance temporary storage with automatic expiration
- **RESTful API**: Clean REST endpoints for storing and retrieving orders
- **Health Check**: Built-in health check endpoint for monitoring
- **Metrics**: Prometheus metrics integration for observability
- **Data Validation**: Comprehensive validation of order structure and payload size limits
- **URL Transformation**: Converts region-specific URLs for data distribution access

### API Endpoints

#### Store Order
- **POST** `/orders`
- Store a new checkout order temporarily
- Accepts JSON-LD formatted order data
- Returns order UUID and expiration time
- **Request Body**: JSON-LD order data with `dcat:dataset` structure
- **Response**: `{"order_id": "uuid", "expires_in_seconds": 7200}`

#### Retrieve Order  
- **GET** `/orders/{order_id}`
- Retrieve a stored order by UUID
- Returns the order data or 404 if expired/not found
- **Response**: `{"order_id": "uuid", "data": [...]}`

#### Health Check
- **GET** `/health-check/`
- Service health status endpoint
- **Response**: `{"status": "OK"}`

#### Metrics
- **GET** `/metrics`
- Prometheus metrics for monitoring

### Configuration

The service can be configured through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDER_TTL_SECONDS` | 7200 | Time to live for orders in seconds (2 hours) |
| `ORDER_KEY_PREFIX` | "order:" | Prefix for Redis keys |
| `MAX_PAYLOAD_SIZE_BYTES` | 10485760 | Maximum payload size (10 MB) |
| `DS_CONNECTOR_BASE_URL` | [see settings.py] | Base URL template for data connector |
| `DATABASE__HOST` | "localhost" | Redis host |
| `DATABASE__PORT` | 6379 | Redis port |
| `DATABASE__DB_NUMBER` | 0 | Redis database number |
| `DATABASE__USERNAME` | None | Redis username (optional) |
| `DATABASE__PASSWORD` | None | Redis password (optional) |

## Architecture

The service follows a clean architecture pattern:

- **REST API Layer**: FastAPI endpoints with request/response validation
- **Use Cases Layer**: Business logic for order management
- **Repository Layer**: Data access abstraction over Redis
- **Models**: Pydantic models for data validation and serialization

### Technology Stack

- **FastAPI**: Modern, fast web framework for Python APIs
- **Redis**: In-memory data structure store for temporary storage
- **Pydantic**: Data validation and serialization
- **Prometheus**: Metrics and monitoring
- **Docker**: Containerization
- **Kubernetes/Helm**: Deployment and orchestration

## Development

### Prerequisites
- Python 3.10+
- Redis server
- Pre-commit (for development)

### Quick Start

1. **Setup Pre-commit Hooks**
```bash
pip install pre-commit
pre-commit install
```

2. **Start Redis** (if not using external Redis)
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally (Ubuntu/Debian)
sudo apt-get install redis-server
sudo systemctl start redis-server
```

3. **Run the Service**
```bash
cd server
pip install -e .
uvicorn app.main:app --reload
```

The service will be available at `http://localhost:8000`

### Example Usage

**Store an Order:**
```bash
curl -X POST "http://localhost:8000/orders" \
     -H "Content-Type: application/json" \
     -d '{
       "data": {
         "dcat:dataset": [
           {
             "region": "eu-west-1",
             "dcat:distribution": [
               {
                 "dcat:accessURL": "https://example.com/data.csv"
               }
             ]
           }
         ]
       }
     }'
```

**Retrieve an Order:**
```bash
curl "http://localhost:8000/orders/{order_id}"
```

### Testing

Run tests for both server and client:
```bash
# Server tests
cd server
pytest

# Client tests  
cd client
pytest
```

## Deployment

The service includes automated CI/CD pipelines that:
- Run code quality checks and tests
- Generate OpenAPI specifications
- Build and push Docker images
- Deploy to Kubernetes clusters using Helm charts
- Publish client packages to PyPI

### Docker

```bash
# Build
docker build -t checkout-service server/

# Run
docker run -d -p 8000:8000 \
  -e DATABASE__HOST=redis-host \
  checkout-service
```

### Kubernetes

Helm charts are available for Kubernetes deployment:
```bash
helm install checkout-service ./charts/server
```

## Working on Components

### Server Development
Go to the `/server` folder to work on the FastAPI backend service.  
Detailed documentation for server setup, dependencies, and development can be found [here](./server/README.md).

### Client Development  
Go to the `/client` folder to work on the Python client library.  
Documentation for client setup, usage examples, and development can be found [here](./client/README.md).

## Data Model

The service expects orders in JSON-LD format following the DCAT (Data Catalog Vocabulary) specification:

```json
{
  "data": {
    "dcat:dataset": [
      {
        "region": "eu-west-1", 
        "dcat:distribution": [
          {
            "dcat:accessURL": "https://example.com/dataset.csv"
          }
        ]
      }
    ]
  }
}
```

### Validation Rules

- Order data cannot be empty
- Must contain `dcat:dataset` as a non-empty array
- Each dataset must have a `region` field
- Each dataset must have `dcat:distribution` as a non-empty array
- Each distribution must have `dcat:accessURL`
- Total payload size must not exceed configured limit (default: 10MB)

## Monitoring and Observability

### Health Checks
- **Endpoint**: `GET /health-check/`
- **Response**: `{"status": "OK"}`
- Use for service availability monitoring

### Metrics
- **Endpoint**: `GET /metrics`
- **Format**: Prometheus metrics
- Includes request counts, response times, and custom business metrics
- Can be scraped by Prometheus for monitoring dashboards

### Logging
Structured logging with configurable levels for:
- Request/response tracking
- Error handling
- Performance monitoring
- Debug information

## Security Considerations

- **Input Validation**: Strict validation of JSON-LD structure and payload sizes
- **UUID-based Access**: Orders are accessible only via their unique UUID
- **Automatic Expiration**: Orders automatically expire after configured TTL
- **No Persistent Storage**: All data is temporary and automatically cleaned up
- **CORS Configuration**: Configurable CORS policies for web applications

## Error Handling

The service provides clear HTTP status codes and error messages:

- **400 Bad Request**: Invalid order data or malformed UUID
- **404 Not Found**: Order not found or expired
- **413 Payload Too Large**: Order data exceeds size limit
- **422 Unprocessable Entity**: Validation errors in request format
- **500 Internal Server Error**: Unexpected server errors

## Performance

- **Redis Backend**: In-memory storage for sub-millisecond response times
- **Async Processing**: Fully asynchronous request handling
- **Connection Pooling**: Efficient Redis connection management
- **Metrics Collection**: Built-in performance monitoring

## Troubleshooting

### Common Issues

**Redis Connection Failed**
```bash
# Check Redis is running
redis-cli ping

# Check connection settings
echo $DATABASE__HOST
echo $DATABASE__PORT
```

**Order Not Found**
- Verify the UUID format is correct
- Check if the order has expired (default TTL: 2 hours)
- Ensure Redis is accessible and data hasn't been flushed

**Payload Too Large**
- Check the `MAX_PAYLOAD_SIZE_BYTES` setting
- Reduce the size of your JSON-LD data
- Consider splitting large datasets into multiple orders

## Release
The application version is specified in the VERSION file. The version should follow the format a.a.a, where 'a' is a number.  
To create a release, update the version in the VERSION file and add a tag in GIT.  
The release version for branches, pull requests, and tags will be generated based on the base version in the VERSION file.

## CI/CD Pipeline

The Checkout Service includes comprehensive GitHub Actions workflows that automatically:

### On Every Push
- **Code Quality**: Lint, format checks, and static analysis
- **Testing**: Run full test suite for both server and client
- **Security**: Dependency vulnerability scanning
- **Documentation**: Generate and validate OpenAPI specifications

### On Release
- **Build**: Create optimized Docker images
- **Package**: Build Python client package for PyPI
- **Deploy**: Deploy to Kubernetes clusters using Helm
- **Publish**: Push client library to PyPI registry

### Workflow Configuration

GitHub Actions can test against multiple Python versions:
```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
```

The pipeline generates:
- Docker images tagged with version and commit SHA
- Helm charts for Kubernetes deployment  
- OpenAPI specifications in YAML/JSON formats
- Python client packages for distribution


**After execution**  
The index.yaml file containing the list of Helm charts will be available at `https://<workspace>.github.io/<project>/helm-charts/index.yaml`. You can this URL on https://artifacthub.io/.  
A package of the client will be available at pypi.org.  
The Docker image will be available at `https://github.com/orgs/<workspace>/packages?repo_name=<project>`.

## Act
You can run your GitHub Actions locally using https://github.com/nektos/act. 

Usage example:
```bash
act push -j test_and_build_client --secret-file my.secrets
```

# Collaboration Guidelines

HIRO uses and requires from its partners [GitFlow with Forks](https://hirodevops.notion.site/GitFlow-with-Forks-3b737784e4fc40eaa007f04aed49bb2e?pvs=4).

## Contributing

1. **Fork the Repository**: Create your own fork of the project
2. **Create Feature Branch**: Use descriptive branch names (e.g., `feature/add-batch-orders`)
3. **Follow Code Standards**: Ensure code passes all pre-commit hooks
4. **Write Tests**: Add tests for new functionality
5. **Update Documentation**: Keep README and API docs current
6. **Submit Pull Request**: Provide clear description of changes

### Code Quality Standards

- **Type Hints**: All Python code must include type annotations
- **Docstrings**: Document all public functions and classes
- **Testing**: Maintain >90% test coverage
- **Formatting**: Use Black, isort, and flake8 for consistent style
