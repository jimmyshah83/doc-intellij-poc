import azure.functions as func
import logging
import uuid
import os
import json
from os.path import join, dirname
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient

app = func.FunctionApp()

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

class Field:
    def __init__(self, key, value, confidence):
        self.key = key
        self.value = value
        self.confidence = confidence

@app.route(route="analyze_doc", auth_level=func.AuthLevel.ANONYMOUS)
def analyze_doc(req: func.HttpRequest) -> func.HttpResponse:

    # Azure Document Intelligencec details
    doc_intelligence_endpoint = os.getenv('DOC_INTELLIGENCE_ENDPOINT')
    doc_intelligence_key = os.getenv('DOC_INTELLIGENCE_KEY')
    req_body = req.get_json()
    formUrl = req_body.get('formurl')

    # Cosmos DB details
    cosmosdb_endpoint = os.getenv("COSMOSDB_ENDPOINT")
    cosmosdb_key = os.getenv("COSMOSDB_KEY")
    cosmosdb_database_name = os.getenv("COSMOSDB_DATABASE_NAME")
    cosmosdb_container_name = os.getenv("COSMOSDB_CONTAINER_NAME")

    # Create form recognizer client
    doc_intelligence_client = DocumentAnalysisClient(
        doc_intelligence_endpoint, AzureKeyCredential(doc_intelligence_key))

    # Start recognizing forms
    poller = doc_intelligence_client.begin_analyze_document_from_url(
        "prebuilt-document", formUrl)
    result = poller.result()

    fields = []
    for kv_pair in result.key_value_pairs:
        if kv_pair.key and kv_pair.value:
            field = Field(kv_pair.key.content,
                          kv_pair.value.content, kv_pair.confidence)
        else:
            field = Field(kv_pair.key.content, "", kv_pair.confidence)
        fields.append(field)

    for field in fields:
        logging.info("Key '{}': Value: '{}', Confidence: {}".format(
            field.key, field.value, field.confidence))

    # Create Cosmos DB client
    cosmos_client = CosmosClient(cosmosdb_endpoint, cosmosdb_key)

    # Insert fields into Cosmos DB
    database = cosmos_client.get_database_client(cosmosdb_database_name)
    container = database.get_container_client(cosmosdb_container_name)

    for field in fields:
        container.create_item(body={
            "id": str(uuid.uuid4()),
            "key": field.key,
            "value": field.value,
            "confidence": field.confidence
        })

    logging.info("Fields inserted into Cosmos DB.")

    response_body = json.dumps([field.__dict__ for field in fields])
    return func.HttpResponse(body=response_body, mimetype="application/json")

@app.route(route="jsdipoc", auth_level=func.AuthLevel.ANONYMOUS)
def jsdipoc(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )