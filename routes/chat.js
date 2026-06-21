const express = require("express");
const router = express.Router();

// Controllers
const { processChat } = require("../controllers/chat.controller");

/* =========================
   CHAT ROUTE (PUBLIC)
========================= */

// POST /api/chat
router.post("/", processChat);

module.exports = router;
