# RetrieveOrderResponse

Response model for retrieve operation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**order_id** | **str** |  | 
**data** | **Dict[str, object]** |  | 

## Example

```python
from template_web_client.models.retrieve_order_response import RetrieveOrderResponse

# TODO update the JSON string below
json = "{}"
# create an instance of RetrieveOrderResponse from a JSON string
retrieve_order_response_instance = RetrieveOrderResponse.from_json(json)
# print the JSON string representation of the object
print RetrieveOrderResponse.to_json()

# convert the object into a dict
retrieve_order_response_dict = retrieve_order_response_instance.to_dict()
# create an instance of RetrieveOrderResponse from a dict
retrieve_order_response_form_dict = retrieve_order_response.from_dict(retrieve_order_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


