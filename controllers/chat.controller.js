const axios = require("axios");

/* =========================
   PROCESS CHAT WITH AI
========================= */
exports.processChat = async (req, res) => {
  try {
    const { message, history } = req.body; // <-- Accept history from React

    if (!message) {
      return res.status(400).json({ error: "Message is required" });
    }

    // Forward the message and history to the Python FastAPI microservice
    const pythonResponse = await axios.post("http://localhost:8000/chat", {
      message: message,
      history: history || [] // <-- Send history to Python
    });

    res.json({ response: pythonResponse.data.response });

  } catch (err) {
    console.error("Error communicating with Python Chatbot Service:", err.message);
    res.status(500).json({ error: "Failed to process chat response" });
  }
};