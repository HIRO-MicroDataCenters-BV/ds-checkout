# template_web_client.OrdersApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**retrieve_order_orders_order_id_get**](OrdersApi.md#retrieve_order_orders_order_id_get) | **GET** /orders/{order_id} | Retrieve checkout order
[**store_order_orders_post**](OrdersApi.md#store_order_orders_post) | **POST** /orders | Store checkout order


# **retrieve_order_orders_order_id_get**
> RetrieveOrderResponse retrieve_order_orders_order_id_get(order_id)

Retrieve checkout order

Retrieve checkout order by UUID  - Retrieves from Redis - Transforms JSON-LD to plain JSON - Returns order data

### Example


```python
import template_web_client
from template_web_client.models.retrieve_order_response import RetrieveOrderResponse
from template_web_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = template_web_client.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with template_web_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = template_web_client.OrdersApi(api_client)
    order_id = 'order_id_example' # str | 

    try:
        # Retrieve checkout order
        api_response = api_instance.retrieve_order_orders_order_id_get(order_id)
        print("The response of OrdersApi->retrieve_order_orders_order_id_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling OrdersApi->retrieve_order_orders_order_id_get: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **order_id** | **str**|  | 

### Return type

[**RetrieveOrderResponse**](RetrieveOrderResponse.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **store_order_orders_post**
> StoreOrderResponse store_order_orders_post(store_order_request)

Store checkout order

Store checkout order temporarily  - Accepts JSON-LD format - Generates UUID - Stores in Redis with TTL - Returns order_id for retrieval

### Example


```python
import template_web_client
from template_web_client.models.store_order_request import StoreOrderRequest
from template_web_client.models.store_order_response import StoreOrderResponse
from template_web_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = template_web_client.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with template_web_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = template_web_client.OrdersApi(api_client)
    store_order_request = template_web_client.StoreOrderRequest() # StoreOrderRequest | 

    try:
        # Store checkout order
        api_response = api_instance.store_order_orders_post(store_order_request)
        print("The response of OrdersApi->store_order_orders_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling OrdersApi->store_order_orders_post: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **store_order_request** | [**StoreOrderRequest**](StoreOrderRequest.md)|  | 

### Return type

[**StoreOrderResponse**](StoreOrderResponse.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

