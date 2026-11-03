# StoreOrderRequest

Request model for storing checkout order

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**data** | **Dict[str, object]** | JSON-LD order data | 

## Example

```python
from template_web_client.models.store_order_request import StoreOrderRequest

# TODO update the JSON string below
json = "{}"
# create an instance of StoreOrderRequest from a JSON string
store_order_request_instance = StoreOrderRequest.from_json(json)
# print the JSON string representation of the object
print StoreOrderRequest.to_json()

# convert the object into a dict
store_order_request_dict = store_order_request_instance.to_dict()
# create an instance of StoreOrderRequest from a dict
store_order_request_form_dict = store_order_request.from_dict(store_order_request_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


