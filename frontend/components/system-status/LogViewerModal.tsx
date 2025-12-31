'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Button,
  Typography,
  Box,
} from '@mui/material';
import {
  Close as CloseIcon,
  ContentCopy as CopyIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';

interface LogViewerModalProps {
  stepName: string;
  log: string;
  onClose: () => void;
}

export default function LogViewerModal({ stepName, log, onClose }: LogViewerModalProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(log);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog
      open={true}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#111827',
          border: '1px solid #1f2937',
          maxHeight: '80vh',
        },
      }}
    >
      <DialogTitle
        sx={{
          bgcolor: '#111827',
          borderBottom: '1px solid #1f2937',
          color: 'white',
          pr: 8,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Step Output Log
        </Typography>
        <Typography variant="body2" sx={{ color: '#9ca3af', mt: 0.5 }}>
          {stepName}
        </Typography>
        <IconButton
          onClick={onClose}
          sx={{
            position: 'absolute',
            right: 8,
            top: 8,
            color: '#9ca3af',
            '&:hover': {
              bgcolor: '#1f2937',
            },
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent
        sx={{
          bgcolor: '#0a0a0a',
          p: 0,
          fontFamily: 'monospace',
          fontSize: '0.875rem',
        }}
      >
        {log ? (
          <Box
            component="pre"
            sx={{
              color: '#d1d5db',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              m: 0,
              p: 3,
            }}
          >
            {log}
          </Box>
        ) : (
          <Box
            sx={{
              color: '#6b7280',
              textAlign: 'center',
              py: 8,
            }}
          >
            No output logs available for this step
          </Box>
        )}
      </DialogContent>

      <DialogActions
        sx={{
          bgcolor: '#111827',
          borderTop: '1px solid #1f2937',
          px: 3,
          py: 2,
          justifyContent: 'space-between',
        }}
      >
        <Typography variant="caption" sx={{ color: '#6b7280' }}>
          Showing last 100 lines of output
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            onClick={copyToClipboard}
            startIcon={copied ? <CheckCircleIcon /> : <CopyIcon />}
            sx={{
              color: copied ? '#10b981' : '#9ca3af',
              bgcolor: '#1f2937',
              textTransform: 'none',
              '&:hover': {
                bgcolor: '#374151',
              },
            }}
          >
            {copied ? 'Copied!' : 'Copy'}
          </Button>
          <Button
            onClick={onClose}
            sx={{
              bgcolor: '#9333ea',
              color: 'white',
              textTransform: 'none',
              '&:hover': {
                bgcolor: '#7e22ce',
              },
            }}
          >
            Close
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
