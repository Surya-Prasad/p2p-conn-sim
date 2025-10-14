from pydantic import BaseModel

# Common models
class endpointModel(BaseModel):
    peer_ip: str
    peer_port: int

class requestedFileModel(BaseModel):
    file_name: str
    file_len: int

class endpointChunkMapModel(BaseModel):
    endpoint: endpointModel
    chunk_indicator_list: list[int]