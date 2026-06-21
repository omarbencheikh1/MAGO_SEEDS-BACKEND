const Product = require("../models/product");
const axios = require("axios");

// --- Helper function to process Gallery and Main Image ---
const processGalleryAndImage = (req) => {
  // 1. Get existing images the user kept (sent as strings)
  let existingGallery = req.body.existingGallery || [];
  if (typeof existingGallery === "string") existingGallery = [existingGallery]; 

  // 2. Get newly uploaded files
  const newFiles = req.files || [];
  const newGalleryPaths = newFiles.map((file) => `/uploads/${file.filename}`);

  // 3. Combine into final gallery array
  const finalGallery = [...existingGallery, ...newGalleryPaths];

  // 4. Determine the main image
  let mainImageIdentifier = req.body.mainImage; // Could be an existing path OR a new file's original name
  let finalImage = null;

  if (mainImageIdentifier) {
    if (existingGallery.includes(mainImageIdentifier)) {
      finalImage = mainImageIdentifier;
    } else {
      const matchedFile = newFiles.find(
        (f) => f.originalname === mainImageIdentifier
      );
      if (matchedFile) finalImage = `/uploads/${matchedFile.filename}`;
    }
  }

  // Fallback if no main image selected but gallery has items
  if (!finalImage && finalGallery.length > 0) {
    finalImage = finalGallery[0];
  }

  return { image: finalImage, gallery: finalGallery };
};

/* =========================
   GET PRODUCTS BY CATEGORY
========================= */
exports.getProductsByCategory = async (req, res) => {
  try {
    const { category } = req.params;

    const products = await Product.find({ category });
    res.json(products);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

/* =========================
   CREATE PRODUCT
========================= */
exports.createProduct = async (req, res) => {
  try {
    const { image, gallery } = processGalleryAndImage(req);

    // Parse specifications if it was sent as a JSON string
    let parsedSpecifications = req.body.specifications;
    if (typeof parsedSpecifications === "string") {
      try {
        parsedSpecifications = JSON.parse(parsedSpecifications);
      } catch (e) {
        parsedSpecifications = [];
      }
    }

    const newProduct = new Product({
      ...req.body,
      image,
      gallery,
      specifications: parsedSpecifications || [] // override with parsed array
    });

    await newProduct.save();

    // Dynamically trigger background vector embedding in FastAPI
    try {
      await axios.post("http://localhost:8000/embed-product", {
        product_id: newProduct._id.toString()
      });
    } catch (embedError) {
      console.error("Embedding sync call failed. Make sure FastAPI is running on Port 8000.", embedError.message);
    }

    res.status(201).json(newProduct);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

/* =========================
   GET ALL PRODUCTS
========================= */
exports.getAllProducts = async (req, res) => {
  try {
    const products = await Product.find();
    res.json(products);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

/* =========================
   GET PRODUCT BY ID
========================= */
exports.getProductById = async (req, res) => {
  try {
    const product = await Product.findById(req.params.id);

    if (!product) {
      return res.status(404).json({ error: "Product not found" });
    }

    res.json(product);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

/* =========================
   UPDATE PRODUCT
========================= */
exports.updateProduct = async (req, res) => {
  try {
    const { image, gallery } = processGalleryAndImage(req);

    // Parse specifications if it was sent as a JSON string
    let parsedSpecifications = req.body.specifications;
    if (typeof parsedSpecifications === "string") {
      try {
        parsedSpecifications = JSON.parse(parsedSpecifications);
      } catch (e) {
        parsedSpecifications = [];
      }
    }

    const updatedData = {
      ...req.body,
      image,
      gallery,
      specifications: parsedSpecifications || [] // override with parsed array
    };

    const product = await Product.findByIdAndUpdate(
      req.params.id,
      updatedData,
      { new: true }
    );

    // Dynamically trigger background vector update in FastAPI
    try {
      await axios.post("http://localhost:8000/embed-product", {
        product_id: product._id.toString()
      });
    } catch (embedError) {
      console.error("Embedding sync call failed. Make sure FastAPI is running on Port 8000.", embedError.message);
    }

    res.json(product);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};


/* =========================
   DELETE PRODUCT
========================= */
exports.deleteProduct = async (req, res) => {
  try {
    await Product.findByIdAndDelete(req.params.id);
    res.json({ message: "Product deleted" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

/* ====================================
   GET RELATED PRODUCTS (AI RECOMMEND)
==================================== */
exports.getRelatedProducts = async (req, res) => {
  try {
    const { id } = req.params;

    // Contact Python microservice to get AI-recommended related items
    const response = await axios.post("http://localhost:8000/related-products", {
      product_id: id
    });

    res.json(response.data);

  } catch (err) {
    console.error("FastAPI AI recommendation service is offline. Falling back to local category match...", err.message);

    // Safe DB fallback: Retrieve products belonging to the same category
    try {
      const currentProduct = await Product.findById(req.params.id);
      if (!currentProduct) {
        return res.status(404).json({ error: "Product not found" });
      }

      const related = await Product.find({
        category: currentProduct.category,
        _id: { $ne: req.params.id }
      }).limit(3);

      res.json(related);

    } catch (dbErr) {
      res.status(500).json({ error: dbErr.message });
    }
  }
};