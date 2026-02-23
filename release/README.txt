Moth-Bench (Windows Portable Edition)
--------------------------------------

Thank you for downloading Moth-Bench!

This is the standalone Windows version of Moth-Bench. 
The application is pre-packaged, meaning you don't need Python 
or any external data files to run the benchmark. Everything 
it needs is built into the .exe file.


WHAT IS MOTH-BENCH?
-------------------
Moth-Bench is a GUI-based benchmark tool designed to measure 
full end-to-end response latency for any LLM endpoint compatible 
with /v1/chat/completions (OpenAI-style API).

The benchmark runs a fixed battery of 43 prompts covering logic, 
math, coding, and reasoning. Upon completion, you can export 
 a beautiful HTML scorecard with a built-in latency leaderboard.


FILES INCLUDED
--------------
moth-bench.exe     - The complete standalone application
README.txt         - This user guide


HOW TO USE
----------
1. Launch the application by double-clicking moth-bench.exe.
2. Enter your model endpoint URL, for example:
       http://127.0.0.1:8081/v1
3. (Optional) Adjust:
       - Max tokens
       - System prompt
4. Click "START MOTH-TEST".
5. Wait for all 43 tests to complete.
6. Export your HTML scorecard when prompted.

The app includes built-in reference benchmarks for models like 
GPT-4o, Llama 3, and Claude, allowing you to see how your 
local hardware measures up against the "pros".


ABOUT REFERENCE DATA
--------------------
The reference values included in the app are community-based 
estimates and are intended as a guide, not official vendor 
benchmarks.


TROUBLESHOOTING
---------------
• App doesn't start:
    Ensure Windows SmartScreen isn't blocking the file 
    (Click "More info" -> "Run anyway").

• Benchmark fails immediately:
    Verify that your endpoint URL is correct and that your 
    local model is running and reachable.

----------------------------------------------------------------
Developed by MothX - 2026