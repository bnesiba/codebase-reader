import json
import os
import uuid
import LLMService

class FileNavService:

    def __init__(self, projectPath):
        self.id = uuid.uuid4().hex
        self.startPath = projectPath
        self.dirStructureString = ""
        self.dirStructureSummary = ""
        self.fileSummaryDict: dict[str,str] = {}
        self.folderSummaryDict: dict[str,str] = {}
        self.projectSummary = ""


    def get_file_summaries(self, dirPath:str):
        keysToGet: list[str] = []
        fileSummaries: list[str] = []
        for summaryKey in self.fileSummaryDict.keys():
            if os.path.dirname(summaryKey).replace("\\", "/").rstrip("/") == dirPath.rstrip("/"):
                keysToGet.append(summaryKey)
        
        for key in keysToGet:
            fileSummaries.append(key + ": " +self.fileSummaryDict[key])
        
        return fileSummaries
    
    def get_folder_summaries(self, dirPath:str):
        keysToGet: list[str] = []
        folderSummaries: list[str] = []
        for summaryKey in self.folderSummaryDict.keys():
            if os.path.dirname(summaryKey).replace("\\", "/").rstrip("/") == dirPath.rstrip("/"):
                keysToGet.append(summaryKey)
        
        for key in keysToGet:
            folderSummaries.append(key + ": " +self.folderSummaryDict[key])
        
        return folderSummaries

    def get_top_5_folder_summaries(self):
        top5 = []
        keysList = sorted(self.folderSummaryDict)
        for i in range(5):
            if(i >= len(keysList)):
                break
            top5.append(keysList[i].replace("\\", "/") + ": " +self.folderSummaryDict[keysList[i]].replace("\\", "/"))
        return top5

    def load_summaries(self, id, projectPath, dirStructureString, dirStructureSummary, fileSummaryDict, folderSummaryDict, projectSummary):
        self.id = id
        self.startPath = projectPath
        self.dirStructureString = dirStructureString
        self.dirStructureSummary = dirStructureSummary
        self.fileSummaryDict = fileSummaryDict
        self.folderSummaryDict = folderSummaryDict
        self.projectSummary = projectSummary
    
    def generate_summaries(self):
        self.generate_dir_structure()
        self.generate_structure_summary()
        self.generate_file_summaries()
        self.generate_directory_summaries()
        self.generate_project_summary()


    def generate_dir_structure(self):
        print("getting directory structure...")
        dirListString = ''

        for root, dirs, files, in os.walk(self.startPath):
            if FileNavService.IsIgnorablePath(root):
                    continue
            level = root.replace(self.startPath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            dirListString = dirListString + '\n{}{}/'.format(indent, os.path.basename(root))
            for file in files:
                dirListString = dirListString + '\n{}{}'.format(indent + '    ', file)
        # print(dirListString)
        self.dirStructureString = dirListString
        return dirListString
    
    def generate_structure_summary(self):
        print("getting structure summary...")
        listStructureSummary = LLMService.evaluateProjectStructure(self.dirStructureString)
        self.dirStructureSummary = listStructureSummary
        self.write_currentdata()
        return listStructureSummary

    def generate_file_summaries(self):
        print("getting file summaries...")
        for root, dirs, files in os.walk(self.startPath):
            if FileNavService.IsIgnorablePath(root):
                continue
        
            for file in files:
                if FileNavService.IsIgnorablePath(file) or not FileNavService.IsReadableFileExtension(file):
                    continue
                print("Summarizing file: " + os.path.join(root, file))
                try:
                    with open(os.path.join(root, file), 'r') as f:
                        fileContent = f.read()
                        summaryString = LLMService.summarizeFile(file, fileContent, self.dirStructureString + '\n' + self.dirStructureSummary).replace("\\", "/")
                        self.fileSummaryDict[os.path.join(root, file).replace("\\", "/")] = summaryString
                except:
                    self.fileSummaryDict[os.path.join(root, file).replace("\\", "/")] = "Could not read file"

        self.write_currentdata()
        return self.fileSummaryDict

    def generate_directory_summaries(self):
        print("getting directory summaries...")
        return self.generate_directory_summary(self.startPath)


    def generate_directory_summary(self,  startPath):
        safeStartpath = startPath.replace("\\", "/")
        for root, dirs, files in os.walk(startPath):
            if FileNavService.IsIgnorablePath(root):
                continue
            
            dirContentSummary = "Summarizing directory: "+ safeStartpath
            for dir in dirs:
                if FileNavService.IsIgnorablePath(dir):
                    continue
                if os.path.join(root, dir) in self.folderSummaryDict.keys():
                    dirContentSummary = dirContentSummary + '\n'+ dir + ' summary: '+ self.folderSummaryDict[os.path.join(root, dir).replace("\\", "/")]
                else:
                    self.generate_directory_summary(os.path.join(root, dir))
                    if os.path.join(root, dir).replace("\\", "/") in self.folderSummaryDict.keys():
                        dirContentSummary = dirContentSummary + '\n'+ dir + ' summary: '+ self.folderSummaryDict[os.path.join(root, dir).replace("\\", "/")]
                    else:
                        dirContentSummary = dirContentSummary + '\n'+ dir + ' summary: '+ "No summary available"

            for file in files:
                if FileNavService.IsIgnorablePath(file) or not FileNavService.IsReadableFileExtension(file):
                    continue
                dirContentSummary = dirContentSummary + '\n' + file + ' summary: ' + self.fileSummaryDict[os.path.join(root, file).replace("\\", "/")]

            if safeStartpath in self.folderSummaryDict.keys():
                continue

            print("Summarizing directory: " + startPath)
            directorySummary = LLMService.summarizeDirectory(safeStartpath, dirContentSummary, self.dirStructureString + "\n\n" + self.dirStructureSummary).replace("\\", "/")
            self.folderSummaryDict[safeStartpath] = directorySummary

        self.write_currentdata()
        return self.folderSummaryDict
    
    def generate_project_summary(self):
        print("getting project summary...")
        self.projectSummary = LLMService.summarizeProject(self.dirStructureString, self.dirStructureSummary, str(self.folderSummaryDict))
        self.write_currentdata()
        return self.projectSummary

    def write_currentdata(self):
        stringifiedData = json.dumps(self.__dict__)
        with open(f'C:\\Users\\brandon.nesiba\\source\\repos\\codebase results\\currentData-{self.id}.txt', 'w') as f:
            f.write(stringifiedData)
            # f.write('{')
            # f.write('id: ' + "\"" + self.id + "\"" + '\n')
            # f.write('startPath: ' + "\"" + self.startPath + "\"" + '\n')
            # f.write('dirStructureString: ' + "\"" + self.dirStructureString + "\"" + '\n')
            # f.write('dirStructureSummary: ' + "\"" + self.dirStructureSummary + "\"" + '\n')
            # f.write('fileSummaryDict: ' + str(self.fileSummaryDict) + '\n')
            # f.write('folderSummaryDict: ' + str(self.folderSummaryDict) + '\n')
            # f.write('projectSummary: ' + "\"" + self.projectSummary + "\"" + '\n')
            # f.write('}')

    @staticmethod
    def load_data_from_file(file):
        with open(file, 'r') as f:
            id = f.readline().strip()
            startPath = f.readline().strip()
            dirStructureString = f.readline().strip()
            dirStructureSummary = f.readline().strip()
            fileSummaryDict = eval(f.readline().strip())
            folderSummaryDict = eval(f.readline().strip())
            fileNav = FileNavService(startPath)
            fileNav.load_summaries(id, startPath, dirStructureString, dirStructureSummary, fileSummaryDict, folderSummaryDict)
            return fileNav

    @staticmethod
    def IsIgnorablePath(string):
        if ".DS_Store" in string:
            return True
        if ".gitingore" in string:
            return True
        if ".git" in string:
            return True
        if ".vscode" in string:
            return True
        if ".idea" in string:
            return True
        if ".venv" in string:
            return True
        if "__pycache__" in string:
            return True
        if "node_modules" in string:
            return True
        if ".vs" in string:
            return True
        if "\\bin" in string:
            return True
        if "/bin" in string:
            return True
        if "\\obj" in string:
            return True
        if "/obj" in string:
            return True
        if ".editorconfig" in string:
            return True
        if ".eslintignore" in string:
            return True
        if "stylelintrc.json" in string:
            return True
        if ".yarnrc" in string:
            return True
        if ".prettierignore" in string:
            return True
        if ".prettierrc" in string:
            return True
        if ".nxignore" in string:
            return True
        if "yarn.lock" in string:
            return True
        if "package-lock.json" in string:
            return True
        if "package.json" in string:
            return True
        if "tsconfig.base.json" in string:
            return True
        if ".gz" in string:
            return True
        if "migrations.json" in string:
            return True
        if "all.css" in string:
            return True
        if "all.min.css" in string:
            return True
        if "duotone." in string:
            return True
        
        return False
    
    @staticmethod
    def IsReadableFileExtension(string):
        if ".cs" in string:
            return True
        if ".json" in string:
            return True
        if ".md" in string:
            return True
        if "js" in string:
            return True
        if ".py" in string:
            return True
        if ".html" in string:
            return True
        if ".css" in string:
            return True
        if ".scss" in string:
            return True
        if ".ts" in string:
            return True
        if ".txt" in string:
            return True
        if ".bat" in string:
            return True
        if ".sh" in string:
            return True
        if ".yaml" in string:
            return True
        if ".csproj" in string:
            return True
        if ".sln" in string:
            return True
        if ".xml" in string:
            return True
        if ".config" in string:
            return True
        
        return False