const jwt = require("jsonwebtoken");

module.exports = (req, res, next) => {
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return res.status(401).json({
      message: "No token",
    });
  }

  try {
    const token = authHeader.replace("Bearer ", "");
    
    // Uses the secure JWT_SECRET from environment variables, falls back to "SECRET_KEY" if undefined
    const decoded = jwt.verify(token, process.env.JWT_SECRET || "SECRET_KEY");

    // Pass user details down to controllers
    req.user = {
      id: decoded.id || decoded._id,
      role: decoded.role, 
    };

    next();
  } catch {
    res.status(401).json({
      message: "Invalid token",
    });
  }
};