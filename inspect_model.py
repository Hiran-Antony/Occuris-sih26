
import torch
import sys
import os

model_path = os.path.abspath('backend/data/models/best_model (2).pth')
if not os.path.exists(model_path):
    print('Model not found at', model_path)
    sys.exit(1)

try:
    state_dict = torch.load(model_path, map_location='cpu')
    
    # If it's a full model object instead of a state_dict, handle it
    if not isinstance(state_dict, dict):
        print('Model is not a state_dict. Type:', type(state_dict))
        if hasattr(state_dict, 'state_dict'):
            state_dict = state_dict.state_dict()
        else:
            sys.exit(0)
            
    # Check YOLOv8 / YOLOv5 structure (often contains 'model', 'ema', 'updates', etc.)
    keys = list(state_dict.keys())
    print('Top level keys:', keys[:20])
    
    if 'model' in state_dict and isinstance(state_dict['model'], torch.nn.Module):
        print('Contains full model object in key model')
        state_dict_inner = state_dict['model'].state_dict()
        inner_keys = list(state_dict_inner.keys())
        print('Inner keys:', inner_keys[:10])
    elif 'model' in state_dict and isinstance(state_dict['model'], dict):
        print('Contains state dict in key model')
        inner_keys = list(state_dict['model'].keys())
        print('Inner keys:', inner_keys[:10])
    elif len(keys) > 0 and 'weight' in keys[0]:
        print('Looks like a raw state_dict')
        print('Keys:', keys[:10])
        
except Exception as e:
    print('Error loading model:', str(e))

