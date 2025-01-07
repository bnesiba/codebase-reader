from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body

import os;
import langchain_openai
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.tools import BaseTool
from typing import Literal
from pydantic import BaseModel, Field
from typing import List
import json
import uuid
from langchain.agents import create_tool_calling_agent
from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from FileNavigationService import FileNavService


vault_secrets = "/vault/secrets/appsecrets.json"
vault_json = json.load(open(vault_secrets))
openai_api_key = vault_json["openAiKey"]


os.environ["OPENAI_API_KEY"] = openai_api_key
llm = ChatOpenAI(model="gpt-4o",temperature=0); #max_tokens=100 ?


##***************** Tool and State Setup *****************##

class CodeSummaryToolContainer():
    def __init__(self, startingPath, FileNav: FileNavService):
        self.startingPath = startingPath;
        self.projectSummaryData = FileNav;
        self.referencedIds = [];
    
    def GetReferencedIds(self):
        return self.referencedIds;

    def _addReferencedId(self,id, refType, date):
        self.referencedIds.append({"Id": id, "refType": refType, "refDate": date});

    def _clearReferencedIds(self):
        self.referencedIds.clear();

    def _getFileSummaryFolders(self):
        return self.projectSummaryData.folderSummaryDict.keys();

    def _getSummariesForFolder(self, folderPath):
        folderSummaries =  self.projectSummaryData.get_folder_summaries(folderPath);
        fileSummaries = self.projectSummaryData.get_file_summaries(folderPath);
        return folderSummaries + fileSummaries

    def GetFolderDetailsToolDef(self):
        class GetSummariesByFolder(BaseModel):
            """gets the summaries for the contents of a specified folder. Use this if you need more specific information on files in that folder. """
            folderPath: Literal[tuple(self._getFileSummaryFolders())] = Field(..., description="The path of the folder to get the detailed summaries for.");
            class Config:
                extra = "forbid" #required for strict = true

        return GetSummariesByFolder;

    def GetFolderDetailsAgentTool(self):
        class GetSummariesByFolderTool(BaseTool):
            name: str = "GetSummariesByFolder"
            description: str = "A tool to get detailed information about a specific communication using the DocumentID from the metadata. Do not run the tool without running GetCommMetadata first."

            def _run(self2, folderPath: Literal[tuple(self._getFileSummaryFolders())]) -> str:
                print(folderPath);
                summaryData = self._getSummariesForFolder(folderPath);
                # self._addReferencedId(idVal, communication[0].metadata["ConversationType"], communication[0].metadata["CommDate"]);

                return f"GetSummariesByFolder({folderPath}) Result:\n {str(summaryData)}."

            def _arun(self2, folderPath) -> str:
                raise NotImplementedError("Async execution not supported yet.")
        
        return GetSummariesByFolderTool();

##***************** EndTool and State Setup *****************##


##***************** CHATBOT RUN DEFINITION *****************##
# **Tool-using Agent Implementation for `GetCommMetadata`,`GetCommunicationDataById`**
# - Uses tools to search communications data. 
def RunCodeSearchBot(userInput, sessionId):
    
    sessionData = sessionDict[sessionId];
    UpdateSessionIdle(sessionId);
    inputData = userInput;

    codeSummaryToolManagement = CodeSummaryToolContainer(sessionFileNavDict[sessionId].startPath,sessionFileNavDict[sessionId])
   
    toolDefList = [codeSummaryToolManagement.GetFolderDetailsToolDef()]; #should also have tools for getting more folder summaries and getting specific files
    agentToolsList = [codeSummaryToolManagement.GetFolderDetailsAgentTool()]; #unfortunate that these can't be the same types

    tooledLLM = llm.bind_tools(toolDefList);

    promptTemplate = ChatPromptTemplate.from_messages(
        [
            ("system", f"""You are a helpful code assistant named Helpy (don't say your name unless directly asked). You are here to help the user better understand the project {sessionFileNavDict[sessionId].startPath}.
             **You are a code assistant. You have tools that give info about the code for the current project. Use those tools to provide consise **SHORT** **As SHORT AS POSSIBLE** accurate answers to user prompts."""),
            ("placeholder", "{chat_history}"),
            ("human", f"Here is the full file structure of the project: \n{sessionFileNavDict[sessionId].dirStructureString}"),
            ("human", f"These are summmaries of the folders in the project: \n{str(sessionFileNavDict[sessionId].folderSummaryDict)}"),#TODO: limit to like top 5 or something
            ("human", f"Here is the overall summary of the project you are working on: \n{sessionFileNavDict[sessionId].projectSummary}"),
            ("human", " If you need additional data about particular files, please run the GetFolderDetails tool to resolve the user prompt **short and consisely**: {input}"),#("human", "{input}"),use simpler one if using display tool (although it also works alright on its own)
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    agent = create_tool_calling_agent(tooledLLM, toolDefList, promptTemplate); #this might not need to be a bound llm. Crazy that the tools need to be in so many places.
    executor = AgentExecutor(agent=agent, tools=agentToolsList, verbose=True);

    inputObject = {"input": inputData};
    if(len(sessionData) > 0):
        print(f"sessionData: {sessionData}");
        inputObject = {"input": inputData, "chat_history": sessionData};
    else:
        print("NO SESSION DATA");
    
    response = executor.invoke(inputObject);
    sessionDict[sessionId].append({"role": "user", "content": inputData});
    sessionDict[sessionId].append({"role": "assistant", "content": response["output"]});
    return {"response": response, "sessionId": sessionId, "references": codeSummaryToolManagement.GetReferencedIds()};

##***************** End CHATBOT RUN DEFINITION *****************##
from datetime import datetime
test = datetime.now();
sessionDict: dict[str,list] = {};
sessionFileNavDict: dict[str,FileNavService] = {};
sessionIdleDict: dict[str,datetime] = {};

def GetSessionId(FileNav: FileNavService):
    sessionId = uuid.uuid4().hex;
    sessionDict[sessionId] = [];
    sessionFileNavDict[sessionId] = FileNav;
    sessionIdleDict[sessionId] = datetime.now();
    return sessionId;

def UpdateSessionIdle(sessionId):
    sessionIdleDict[sessionId] = datetime.now();

def removeSession(sessionId):
    del sessionDict[sessionId];
    del sessionFileNavDict[sessionId];
    del sessionIdleDict[sessionId];

def cleanupIdleSessions():
    idleSessions = [];
    for sessionId in sessionDict.keys():
        if (datetime.now() - sessionIdleDict[sessionId]).seconds > 3600:
            idleSessions.append(sessionId);

    for sessionId in idleSessions:
        removeSession(sessionId);
