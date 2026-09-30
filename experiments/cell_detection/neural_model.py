"""Conservative adaptation of the original, unchanged MobileNet architecture.

Only feature blocks 10--12 receive gradients. BatchNorm's running means and
variances stay fixed; it still uses the original inference statistics.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from detector import Encoder


CHECKPOINT_VERSION = 1
ARCHITECTURE = 'torchvision-mobilenet-v3-small-imagenet1k-v1-96px'
FIRST_TRAINABLE_BLOCK = 10


def tensor_hash(values):
    digest=hashlib.sha256()
    for name,value in sorted(values.items()):
        digest.update(name.encode())
        array=value.detach().cpu().contiguous().numpy()
        digest.update(str(array.dtype).encode());digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def prefix_state(features):
    return {name:value for name,value in features.state_dict().items()
            if int(name.split('.')[0])<FIRST_TRAINABLE_BLOCK}


def batchnorm_buffers(features):
    return {name:value for name,value in features.state_dict().items()
            if name.endswith(('running_mean','running_var','num_batches_tracked'))}


def trainable_suffix(encoder):
    features=encoder.model.features
    features.eval()
    for parameter in features.parameters():parameter.requires_grad_(False)
    suffix=features[FIRST_TRAINABLE_BLOCK:]
    for parameter in suffix.parameters():parameter.requires_grad_(True)
    suffix.eval()
    return features[:FIRST_TRAINABLE_BLOCK],suffix


def suffix_embeddings(suffix, prefix):
    import torch.nn.functional as functional
    return functional.normalize(suffix(prefix).mean(dim=(2,3)),dim=1)


def adaptation_loss(embeddings, teacher, triplets, margin=.2, preservation=.1):
    """Compare filled/filled and filled/empty within each one scene.

    The preservation term discourages moving far from the original embeddings.
    It is not proof of preserved real-image accuracy; that requires evaluation.
    """
    import torch
    anchor,positive,negative=embeddings[triplets[:,0]],embeddings[triplets[:,1]],embeddings[triplets[:,2]]
    ranking=torch.relu(margin+(anchor*negative).sum(1)-(anchor*positive).sum(1)).mean()
    preserve=(1-(embeddings*teacher).sum(1)).mean()
    return ranking+preservation*preserve,ranking,preserve


def changed_tensors(before, after):
    changes={}
    for name,value in before.items():
        difference=after[name].detach().cpu()-value
        if not np.array_equal(after[name].detach().cpu().numpy(),value.numpy()):
            changes[name]=float(difference.float().norm())
    return changes


def save_checkpoint(path, encoder, metadata):
    import torch
    path=Path(path)
    if path.exists():raise ValueError('Checkpoint already exists; choose a new output path.')
    payload={'format_version':CHECKPOINT_VERSION,'architecture':ARCHITECTURE,
             'feature_state':{name:value.detach().cpu().clone() for name,value in encoder.model.features.state_dict().items()},
             'metadata':metadata}
    torch.save(payload,path)


class FineTunedEncoder(Encoder):
    def __init__(self,checkpoint,threads=4):
        super().__init__(threads=threads)
        payload=self.torch.load(checkpoint,map_location='cpu',weights_only=True)
        if (not isinstance(payload,dict) or set(payload)!={'format_version','architecture','feature_state','metadata'} or
                payload['format_version']!=CHECKPOINT_VERSION or payload['architecture']!=ARCHITECTURE):
            raise ValueError('Unsupported neural checkpoint format or architecture.')
        original_prefix=tensor_hash(prefix_state(self.model.features))
        original_bn=tensor_hash(batchnorm_buffers(self.model.features))
        if (payload['metadata'].get('frozen_prefix_sha256')!=original_prefix or
                payload['metadata'].get('batchnorm_buffers_sha256')!=original_bn):
            raise ValueError('Neural checkpoint does not preserve the original prefix and BatchNorm statistics.')
        self.model.features.load_state_dict(payload['feature_state'],strict=True)
        if (tensor_hash(prefix_state(self.model.features))!=original_prefix or
                tensor_hash(batchnorm_buffers(self.model.features))!=original_bn):
            raise ValueError('Neural checkpoint altered frozen layers or BatchNorm statistics.')
        self.model.eval()
        self.checkpoint_metadata=payload['metadata']
