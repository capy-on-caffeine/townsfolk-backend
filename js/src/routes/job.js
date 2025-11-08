import express from 'express';
import Job from '../models/Job.js';
import Persona from '../models/Persona.js';
import Feedback from '../models/Feedback.js';
import fetch from 'node-fetch';

const router = express.Router();

const serviceLink = process.env.EXTERNAL_SERVICE_URL;

// Start a new job
router.post('/start', async (req, res) => {
  try {
    const { mvpLink } = req.body;
    
    // Create a new job with auto-generated _id
    const job = new Job();
    await job.save();

    // Fetch all personas
    const personas = await Persona.find();
    
    // Make request to the external service
    const response = await fetch(serviceLink, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        mvpLink: mvpLink,
        jobId: job._id,
        personas
      })
    });

    if (!response.ok) {
      throw new Error('Failed to start job with external service');
    }

    // Update job status to in-progress
    job.status = 'in-progress';
    await job.save();

    res.status(201).json(job);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// Get job status
router.get('/:jobId/status', async (req, res) => {
  try {
    const { jobId } = req.params;
    const job = await Job.findById(jobId);
    
    if (!job) {
      return res.status(404).json({ message: 'Job not found' });
    }

    // You can add the external service URL in your environment variables
    const statusUrl = `${serviceLink}/status/${jobId}`;
    const response = await fetch(statusUrl);
    
    if (!response.ok) {
      throw new Error('Failed to fetch job status from external service');
    }

    const statusData = await response.json();
    
    // Optionally update job status based on external service response
    if (statusData.status !== job.status) {
      job.status = statusData.status;
      await job.save();
    }

    res.json(statusData);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// Get job feedback
router.get('/:jobId/feedback', async (req, res) => {
  try {
    const { jobId } = req.params;
    const feedback = await Feedback.find({ job: jobId })
      .populate('persona')
      .sort({ createdAt: -1 });
    
    res.json(feedback);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

export default router;