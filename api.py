
#!/usr/bin/env python3.9
import json
import logging
import os
from typing import Optional
import fastapi
from pydantic import BaseModel, Field
from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body

import langchain_openai
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.tools import BaseTool
from typing import Literal
from typing import List
import uuid
import asyncio

import CodeReaderChatService
import LLMService
from FileNavigationService import FileNavService

# Log filtering config: Filter out access logs for /health and /openapi.json

class ReadinessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/ready") == -1

class LivenessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/self") == -1

class MetricsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/metrics") == -1

class OpenAPIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/openapi.json") == -1

logging.getLogger("uvicorn.access").addFilter(ReadinessFilter())
logging.getLogger("uvicorn.access").addFilter(LivenessFilter())
logging.getLogger("uvicorn.access").addFilter(MetricsFilter())
logging.getLogger("uvicorn.access").addFilter(OpenAPIFilter())


# FastAPI models

def getVersionNumber() -> str:
    """Get version number from a file in the repo. To be populated by the CI/CD
    pipeline.
    """
    with open('./version') as f:
        version = f.read().rstrip()

    return version

def getRootPath() -> str:
    """Get the root path from the environment if it exists. Otherwise leave it
    blank.
    """

    baseHref = os.environ.get('BASE_HREF')

    return baseHref if baseHref is not None else ""
    
    

# Create the app here
app = fastapi.FastAPI(
        title='CodeReaderApi', # API docs title
        description='Api interface for Code reader chatbot', # API description
        version=getVersionNumber(),
        root_path=getRootPath(),
        docs_url='/swagger',
        )
origins = ["*"];
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Task to clean up idle sessions
async def cleanup_sessions():
    while True:
        CodeReaderChatService.cleanupIdleSessions();
        print("Cleaning up idle sessions...")
        await asyncio.sleep(1800)

@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(cleanup_sessions())

# Use decorators to define the HTTP method
@app.get(
        '/self',
        summary="Liveness probe.",
        tags=['Health']
        )
def api_sel():
    return "OK"

@app.get(
        '/ready',
        summary="Readiness probe",
        tags=['Health']
        )
def api_ready():
    return "OK"

##***************** FastAPI endpoint Setup *****************##
#defining endpoints for REST controllers/routes in the API

@app.get("/")
def read_root():
    return {"Hello": "World"}



@app.post("/codeReader/helloWorld")
def run_hello(message: str = Body()):
    return LLMService.askChatGPT(message)


@app.post("/codeReader/GetSummarized")
def get_summarized(startingPath: str = Body()):
    fileNav = FileNavService(startingPath)
    fileNav.generate_summaries()
    returnString = "FileStructure:\n"+ fileNav.dirStructureString + "\n"
    returnString = returnString + "FileStructureSummary: \n" + fileNav.dirStructureSummary
    returnString = returnString + "\n\nFileSummaries: \n\n"
    for key in fileNav.fileSummaryDict:
        returnString = returnString + key + ":\n" + fileNav.fileSummaryDict[key] + "\n\n"
    returnString = returnString + "\n\nFolderSummaries:\n\n"
    for key in fileNav.folderSummaryDict:
        returnString = returnString + key + ":\n" + fileNav.folderSummaryDict[key] + "\n\n"
    returnString = returnString + "\n\nProjectSummary:\n\n" + fileNav.projectSummary
    return returnString
    # return LLMService.evaluateProjectStructure(dirStructString)

@app.post("/codeReader/NewSession")
def new_session(startingPath: str = Body()):
    fileNav = FileNavService(startingPath)
    fileNav.generate_summaries()
    return CodeReaderChatService.GetSessionId(fileNav)

# @app.post("/codeReader/ImportSession")
# def import_session(fileNavString: str = Body()):
#     importFileNav = json.loads(fileNavString)
#     session = FileNavService("")
#     session.load_summaries(importFileNav["id"], importFileNav["startPath"], importFileNav["dirStructureString"], importFileNav["dirStructureSummary"], importFileNav["fileSummaryDict"], importFileNav["folderSummaryDict"], importFileNav["projectSummary"])
#     return CodeReaderChatService.GetSessionId(session)

@app.post("/codeReader/ImportSessionObj")
def import_session(fileNav = Body()):
    importFileNav = fileNav
    session = FileNavService("")
    session.load_summaries(importFileNav["id"], importFileNav["startPath"], importFileNav["dirStructureString"], importFileNav["dirStructureSummary"], importFileNav["fileSummaryDict"], importFileNav["folderSummaryDict"], importFileNav["projectSummary"])
    return CodeReaderChatService.GetSessionId(session)


# @app.get("/commSearch/details/{item_id}")
# def read_item(item_id):
#     return CodeReaderService.GetDocumentDetails(item_id);

@app.post("/codeReader/Chat/{sessionId}")
def run_chat(sessionId, message: str = Body()):
    return CodeReaderChatService.RunCodeSearchBot(message, sessionId);

@app.post("/codeReader/init/")
def init_search(startingPath: str = Body()):
    fileNav = FileNavService(startingPath)
    fileNav.generate_summaries()
    sessionId =  CodeReaderChatService.GetSessionId(fileNav)
    return CodeReaderChatService.RunCodeSearchBot("Welcome the user and provide a short overview of the languages/tools used in the project and what it does.", sessionId)

@app.post("/codeReader/init/{sessionId}")
def init_search_session(sessionId,startingPath: str = Body()):
    return CodeReaderChatService.RunCodeSearchBot("Welcome the user and provide a short overview of the languages/tools used in the project and what it does.", sessionId)
    

##***************** End FastAPI Setup *****************##
