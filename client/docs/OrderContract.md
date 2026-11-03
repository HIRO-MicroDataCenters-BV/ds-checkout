# OrderContract

A contract issued for (part of) an order by one region's generator.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**region** | **str** | Region whose datasets it covers, e.g. hus | 
**jti** | **str** | Contract id, as listed in the Clearing House | 
**token** | **str** | The signed contract (VC-JWT) | 

## Example

```python
from template_web_client.models.order_contract import OrderContract

# TODO update the JSON string below
json = "{}"
# create an instance of OrderContract from a JSON string
order_contract_instance = OrderContract.from_json(json)
# print the JSON string representation of the object
print OrderContract.to_json()

# convert the object into a dict
order_contract_dict = order_contract_instance.to_dict()
# create an instance of OrderContract from a dict
order_contract_form_dict = order_contract.from_dict(order_contract_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


