#!/bin/bash
cd ~/repos/cowabunga_bakes
npx serve docs -p 3000 &
sleep 2
open -a "Google Chrome" http://localhost:3000/gallery
wait