# StoreOrderResponse

Response model for store operation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**order_id** | **str** | UUID of the stored order | 
**expires_in_seconds** | **int** | TTL in seconds | 

## Example

```python
from template_web_client.models.store_order_response import StoreOrderResponse

# TODO update the JSON string below
json = "{}"
# create an instance of StoreOrderResponse from a JSON string
store_order_response_instance = StoreOrderResponse.from_json(json)
# print the JSON string representation of the object
print StoreOrderResponse.to_json()

# convert the object into a dict
store_order_response_dict = store_order_response_instance.to_dict()
# create an instance of StoreOrderResponse from a dict
store_order_response_form_dict = store_order_response.from_dict(store_order_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


