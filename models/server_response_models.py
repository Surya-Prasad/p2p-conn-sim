from pydantic import BaseModel
from models.common_models import endpointModel, requestedFileModel, endpointChunkMapModel
from typing import Dict,List

# Model for REGISTER_REPLY
class FileRegisterReply(BaseModel):
    status: str
    message: str

# Model for FILE_LIST_REPLY
class FileListReply(BaseModel):
    number_of_files: int
    files_list: requestedFileModel



# Model for FILE_LOCATIONS_REPLY
class FileLocationsReply(BaseModel):
    number_of_peers: int
    chunk_endpoint_map: Dict[str,List]

# Model for CHUNK_REGISTER_REPLY
class ChunkRegisterReply(BaseModel):
    status: str
    message: str

# Model for File Chunk Reply
class FileChunkReply(BaseModel):
    chunk_data: bytes
