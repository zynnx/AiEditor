import os

lines = []
lines.append('"""Export service – receives TimelineEvents and builds FFmpeg cuts.')
lines.append('.')
lines.append('This service NEVER decides what to export.')
lines.append('It only receives already selected TimelineEvents from the controller.')
lines.append('.')
lines.append('Supported backends: NVENC, H26