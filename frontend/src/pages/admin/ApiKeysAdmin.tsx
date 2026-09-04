import { useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Form, Row, Table } from 'react-bootstrap';

import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/shared/queries/apiKeys';

const getErrorMessage = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

const ApiKeysAdmin = () => {
  const [error, setError] = useState('');

  const [createName, setCreateName] = useState('');
  const [createScopes, setCreateScopes] = useState('');
  const [createdKey, setCreatedKey] = useState('');

  const apiKeysQuery = useApiKeys();
  const createApiKeyMutation = useCreateApiKey();
  const revokeApiKeyMutation = useRevokeApiKey();

  const sortedItems = useMemo(
    () => [...(apiKeysQuery.data || [])].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [apiKeysQuery.data]
  );

  const onCreate = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setCreatedKey('');

    const name = createName.trim();
    if (!name) {
      setError('Name is required');
      return;
    }

    const scopes = createScopes
      .split(',')
      .map((scope) => scope.trim())
      .filter(Boolean);

    try {
      const created = await createApiKeyMutation.mutateAsync({ name, scopes });
      setCreatedKey(created?.api_key || '');
      setCreateName('');
      setCreateScopes('');
    } catch (error) {
      setError(getErrorMessage(error, 'Failed to create API key'));
    }
  };

  const onRevoke = async (keyId: string) => {
    setError('');
    try {
      await revokeApiKeyMutation.mutateAsync(keyId);
    } catch (error) {
      setError(getErrorMessage(error, 'Failed to revoke API key'));
    }
  };

  const isBusy =
    apiKeysQuery.isLoading || createApiKeyMutation.isPending || revokeApiKeyMutation.isPending;

  return (
    <div className="p-3">
      <h4 className="mb-3">API Keys</h4>
      <Row className="g-4">
        <Col lg={5}>
          <Card>
            <Card.Body>
              <Card.Title>Create API Key</Card.Title>
              <Card.Text className="text-muted">
                Key value is only shown once. Save it securely.
              </Card.Text>

              <Form onSubmit={onCreate}>
                <Form.Group className="mb-3" controlId="apiKeyName">
                  <Form.Label>Name</Form.Label>
                  <Form.Control
                    type="text"
                    value={createName}
                    onChange={(e) => setCreateName(e.target.value)}
                    maxLength={120}
                    placeholder="e.g. docs-test-key"
                    required
                  />
                </Form.Group>

                <Form.Group className="mb-3" controlId="apiKeyScopes">
                  <Form.Label>Scopes (optional)</Form.Label>
                  <Form.Control
                    type="text"
                    value={createScopes}
                    onChange={(e) => setCreateScopes(e.target.value)}
                    placeholder="comma,separated,scopes"
                  />
                </Form.Group>

                <Button type="submit" disabled={createApiKeyMutation.isPending}>
                  {createApiKeyMutation.isPending ? 'Creating...' : 'Create Key'}
                </Button>
              </Form>

              {createdKey && (
                <Alert variant="success" className="mt-3 mb-0">
                  <div className="fw-semibold">New key (copy now):</div>
                  <code>{createdKey}</code>
                </Alert>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col lg={7}>
          <Card>
            <Card.Body>
              <Card.Title>Existing API Keys</Card.Title>

              {(error || apiKeysQuery.error) && (
                <Alert variant="danger">{error || apiKeysQuery.error?.message}</Alert>
              )}

              <div className="table-responsive">
                <Table striped bordered hover size="sm" className="mb-0 align-middle">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Scopes</th>
                      <th>Created</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apiKeysQuery.isLoading && (
                      <tr>
                        <td colSpan={5} className="text-center text-muted py-3">
                          Loading API keys...
                        </td>
                      </tr>
                    )}
                    {!apiKeysQuery.isLoading && sortedItems.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center text-muted py-3">
                          No API keys yet.
                        </td>
                      </tr>
                    )}
                    {sortedItems.map((item) => {
                      const revoked = Boolean(item.revoked_at);
                      return (
                        <tr key={item.id}>
                          <td>{item.name}</td>
                          <td>{(item.scopes || []).join(', ') || '-'}</td>
                          <td>
                            {item.created_at ? new Date(item.created_at).toLocaleString() : '-'}
                          </td>
                          <td>{revoked ? 'Revoked' : 'Active'}</td>
                          <td>
                            {!revoked ? (
                              <Button
                                variant="outline-danger"
                                size="sm"
                                disabled={isBusy}
                                onClick={() => onRevoke(item.id)}
                              >
                                {revokeApiKeyMutation.isPending &&
                                revokeApiKeyMutation.variables === item.id
                                  ? 'Revoking...'
                                  : 'Revoke'}
                              </Button>
                            ) : (
                              '-'
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ApiKeysAdmin;
