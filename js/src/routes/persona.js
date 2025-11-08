import express from 'express';
import Persona from '../models/Persona.js';

const router = express.Router();

// Feed single persona to DB
router.post('/', async (req, res) => {
  try {
    const persona = new Persona(req.body);
    await persona.save();
    res.status(201).json(persona);
  } catch (error) {
    res.status(400).json({ message: error.message });
  }
});

// Feed multiple personas to DB
router.post('/batch', async (req, res) => {
  try {
    const personas = await Persona.insertMany(req.body);
    res.status(201).json(personas);
  } catch (error) {
    res.status(400).json({ message: error.message });
  }
});

// Fetch one persona
router.get('/:id', async (req, res) => {
  try {
    const persona = await Persona.findById(req.params.id);
    if (!persona) {
      return res.status(404).json({ message: 'Persona not found' });
    }
    res.json(persona);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// Fetch multiple personas based on query
router.get('/', async (req, res) => {
  try {
    const query = req.query;
    const personas = await Persona.find(query);
    res.json(personas);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

export default router;