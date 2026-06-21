const express = require("express");
const router = express.Router();

// Middleware
const auth = require("../middleware/auth");
const upload = require("../middleware/upload");

// Controllers
const {
  isAdmin,
} = require("../controllers/user.controller");

const {
  getProductsByCategory,
  createProduct,
  getAllProducts,
  deleteProduct,
  updateProduct,
  getProductById,
  getRelatedProducts, // Imported the new related products controller
} = require("../controllers/products.controller");

/* =========================
   GET ROUTES (PUBLIC)
========================= */

// Get all products
router.get("/", getAllProducts);

// Get products by category
router.get("/category/:category", getProductsByCategory);

// Get related products (AI Recommended)
router.get("/:id/related", getRelatedProducts);

// Get product by ID
router.get("/:id", getProductById);

/* =========================
   ADMIN ROUTES (PROTECTED)
========================= */

// Create product (Accept up to 3 images in the 'newGallery' field)
router.post(
  "/",
  auth,
  isAdmin,
  upload.array("newGallery", 3),
  createProduct
);

// Update product
router.put(
  "/:id",
  auth,
  isAdmin,
  upload.array("newGallery", 3),
  updateProduct
);


// Delete product
router.delete(
  "/:id",
  auth,
  isAdmin,
  deleteProduct
);

module.exports = router;