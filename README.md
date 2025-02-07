

# Introduction

rw is a cli to port the function rec_wizard into python 


## Known Bugs

In Kubuntu, you will need to install support for pyaudio:


To successfully install PyAudio, you need to ensure that the `portaudio`
library and development headers are installed on your system. You can follow
these steps to resolve the issue:

1. Install PortAudio:
   
   On Ubuntu/Kubuntu, you can install the `portaudio` library and development headers using the package manager. Run the following command to install `portaudio19-dev`, which includes the necessary development headers and libraries:
   
   ```
   sudo apt update
   sudo apt install portaudio19-dev
   ```
