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
        keysList: list[str] = [];
        for key in self.projectSummaryData.folderSummaryDict.keys():
            keysList.append(key);
        
        return keysList;

    def _getFilePaths(self):
        keysList: list[str] = [];
        for key in self.projectSummaryData.fileSummaryDict.keys():
            keysList.append(key);
        
        return keysList;

    def _getSummariesForFolder(self, folderPath):
        folderSummaries =  self.projectSummaryData.get_folder_summaries(folderPath);
        fileSummaries = self.projectSummaryData.get_file_summaries(folderPath);
        return folderSummaries + fileSummaries

    def GetFolderDetailsToolDef(self):
        class GetSummariesByFolder(BaseModel):
            f"""gets the summaries for the contents of a specified folder. Use this if you need more specific information on files in that folder. Must be one of: {str(self._getFileSummaryFolders())}"""
            folderPath: Literal[tuple(self._getFileSummaryFolders())] = Field(..., description="The path of the folder to get the detailed summaries for.");
            class Config:
                extra = "forbid" #required for strict = true

        return GetSummariesByFolder;

    def GetFolderDetailsAgentTool(self):
        class GetSummariesByFolderTool(BaseTool):
            name: str = "GetSummariesByFolder" 
            description: str = f"A tool to get the detailed summaries for each of the contents of a specified folder. Must be one of: {str(self._getFileSummaryFolders())}"

            def _run(self2, folderPath: Literal[tuple(self._getFileSummaryFolders())]) -> str:
                print(f"Getting summaries for folder: {folderPath}");
                print("data: "+ str(self.projectSummaryData.folderSummaryDict.keys()));
                summaryData = self._getSummariesForFolder(folderPath)
                # self._addReferencedId(idVal, communication[0].metadata["ConversationType"], communication[0].metadata["CommDate"]);

                return f"GetSummariesByFolder({folderPath}) Result:\n {str(summaryData)}."

            def _arun(self2, folderPath) -> str:
                raise NotImplementedError("Async execution not supported yet.")
        
        return GetSummariesByFolderTool();

    def GetFileContentToolDef(self):
        class GetFileContent(BaseModel):
            f"""gets the contents of a specified file. Use this if you need more specific information on files in that folder. Only use if you need specific content. Otherwise get the summaries first."""
            filePath: Literal[tuple(self._getFilePaths())] = Field(..., description="The path of the file to get the content of.");
            class Config:
                extra = "forbid" #required for strict = true

        return GetFileContent;

    def GetFileContentAgentTool(self):
        class GetFileContentTool(BaseTool):
            name: str = "GetFileContent" 
            description: str = f"A tool to get the detailed summaries for each of the contents of a specified folder. Only use this tool if you *need* to access the contents of the file. The folder summaries may be sufficient."

            def _run(self2, filePath: Literal[tuple(self._getFilePaths())]) -> str:
                print(f"Getting file content for file: {filePath}");
                if filePath not in self._getFilePaths():
                    return f"GetFileContent({filePath}) Result:\n File not found in project. - Make sure the path you selected is valid.";
            
                fileContent = open(filePath, "r").read();
                # self._addReferencedId(idVal, communication[0].metadata["ConversationType"], communication[0].metadata["CommDate"]);

                return f"GetFileContent({filePath}) Result:\n {str(fileContent)}."

            def _arun(self2, filePath) -> str:
                raise NotImplementedError("Async execution not supported yet.")
        
        return GetFileContentTool();

##***************** EndTool and State Setup *****************##


##***************** CHATBOT RUN DEFINITION *****************##
# **Tool-using Agent Implementation for `GetCommMetadata`,`GetCommunicationDataById`**
# - Uses tools to search communications data. 
def RunCodeSearchBot(userInput, sessionId):
    
    # print(str(sessionDict));
    sessionData = sessionDict[sessionId];
    UpdateSessionIdle(sessionId);
    inputData = userInput;

    codeSummaryToolManagement = CodeSummaryToolContainer(sessionFileNavDict[sessionId].startPath,sessionFileNavDict[sessionId])
   
    toolDefList = [codeSummaryToolManagement.GetFolderDetailsToolDef(), codeSummaryToolManagement.GetFileContentToolDef()]; 
    agentToolsList = [codeSummaryToolManagement.GetFolderDetailsAgentTool(), codeSummaryToolManagement.GetFileContentAgentTool()]; #unfortunate that these can't be the same types

    tooledLLM = llm.bind_tools(toolDefList, strict= True);

    top5Dir = str(sessionFileNavDict[sessionId].get_top_5_folder_summaries())
    infoString = f"""Here is the full file structure of the project: \n{sessionFileNavDict[sessionId].dirStructureString}
    These are summmaries of some of the higher-level folders in the project: \n{top5Dir}
    Here is the overall summary of the project you are working on: \n{sessionFileNavDict[sessionId].projectSummary}

"""
    
    folderToolInstructionString = f"\nGetSummariesByFolder is a tool that provides detailed summaries of the contents of a specified folder. Input path must be one of: {str(codeSummaryToolManagement._getFileSummaryFolders())}\n";
    fileToolInstructionString = f"\nGetFileContent is a tool that provides the content of a specified file. *Only use this tool if the summaries are insufficient.* Input path must be one of: {str(codeSummaryToolManagement._getFilePaths())}";

    promptTemplate = ChatPromptTemplate.from_messages(
        [
            ("system", """You are a helpful code assistant named Helpy (don't say your name unless directly asked). You are here to help the user (who is a software engineer) better understand the project.
             **You are a code assistant. You have tools that give info about the code for the current project. Use those tools to provide consise **SHORT** **As SHORT AS POSSIBLE** accurate answers to user prompts.
             """ + folderToolInstructionString + fileToolInstructionString),
            ("placeholder", "{chat_history}"),
            ("human", infoString + "If you need additional data about particular files, please run the GetSummariesByFolder and GetFileContent tools. to resolve the user prompt **short and consisely**: {input}"),#("human", "{input}"),use simpler one if using display tool (although it also works alright on its own)
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
    print(response)
    sessionDict[sessionId].append({"role": "user", "content": inputData});
    sessionDict[sessionId].append({"role": "assistant", "content": response["output"]});
    return {"message": response["output"], "sessionId": sessionId, "references": codeSummaryToolManagement.GetReferencedIds()};

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
