var express = require('express');
var router = express.Router();
const auth = require("../middleware/auth");
const User = require("../models/user.model");
const { isAdmin } = require("../controllers/user.controller");
const userController = require('../controllers/user.controller');
/* GET users listing. */
router.get('/getAllUsers', userController.getAllUsers);
router.post('/addUserClient', userController.addUserClient);
router.post('/addUserAdmin', userController.addUserAdmin);
router.delete('/deleteUser/:id', userController.deleteUser);
router.get('/getUserById/:id', userController.getUserById);
router.post("/register", userController.register);
router.post("/login", userController.login);
router.get("/me", auth, userController.getCurrentUser);

router.put("/avatar", auth, userController.changeAvatar);

router.get("/my-orders", auth, userController.getMyOrders);

router.get("/my-reviews", auth,userController.getMyReviews
);

router.put("/settings", auth, userController.updateSettings);

router.put('/updateUser/:id', auth, isAdmin, userController.updateUser);

module.exports = router;
