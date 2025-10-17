from pydantic import BaseModel
from typing import Optional, List
from models.common_models import endpointModel, requestedFileModel

# Model for REGISTER_REQUEST 
class RegisterRequest(BaseModel):
    endpoint: endpointModel
    number_of_files_to_register: int
    files: list[requestedFileModel] 

# Model for FILE_LIST_REQUEST
class FileListRequest(BaseModel):
    requested_file_list: Optional[List[requestedFileModel]] = None

# Model for FILE_LOCATIONS_REQUEST
class FileLocationsRequest(BaseModel):
    file_name: str

# Model for CHUNK_REGISTER_REQUEST
class ChunkRegisterRequest(BaseModel):
    chunk_indicator: int
    new_seeder_endpoint: endpointModel
    file_name: str

# Model for File Chunk Request
class FileChunkRequest(BaseModel):
    file: requestedFileModel
    chunk_indicator: int

