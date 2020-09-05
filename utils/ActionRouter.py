class ActionRouter:
	def __init__(self):
		self.routes = {}
	
	def __call__(self, func):
		self.routes[func.__name__] = func
		return func
	
	'''
	def callWithArgs(self, action):
		def decorator(func):
			self.routes[action] = func
			return func
		return decorator
	'''
	
	async def route(self, action, *arg, **kw):
		if action in self.routes:
			await self.routes[action](*arg, **kw)
		else:
			raise ValueError(f"The action <{action}> has not been registered")
